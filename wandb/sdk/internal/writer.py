"""Writer thread."""

import logging
from typing import TYPE_CHECKING, Optional, Callable

from ..lib import tracelog, proto_util
from . import context, datastore, flow_control
from .settings_static import SettingsStatic

if TYPE_CHECKING:
    from queue import Queue

    from wandb.proto.wandb_internal_pb2 import Record, Result, SenderStatusReportRequest


logger = logging.getLogger(__name__)


class WriteManager:
    _settings: SettingsStatic
    _record_q: "Queue[Record]"
    _result_q: "Queue[Result]"
    _sender_q: "Queue[Record]"
    _ds: Optional[datastore.DataStore]
    _flow_control: Optional[flow_control.FlowControl]
    _sender_status_report: Optional["SenderStatusReportRequest"]
    _context_keeper: context.ContextKeeper

    def __init__(
        self,
        settings: SettingsStatic,
        record_q: "Queue[Record]",
        result_q: "Queue[Result]",
        sender_q: "Queue[Record]",
        context_keeper: context.ContextKeeper,
    ):
        self._settings = settings
        self._record_q = record_q
        self._result_q = result_q
        self._sender_q = sender_q
        self._context_keeper = context_keeper
        self._ds = None
        self._flow_control = None
        # self._debug = False
        self._sender_status_report = None
        self._debug = True

    def open(self) -> None:
        self._ds = datastore.DataStore()
        self._ds.open_for_write(self._settings.sync_file)
        debug_kwargs = dict(
            _threshold_bytes_high=1000,
            _threshold_bytes_mid=500,
            _threshold_bytes_low=200,
            _mark_granularity_bytes=100,
            _recovering_bytes_min=300,
        )
        kwargs = debug_kwargs if self._debug else {}
        self._flow_control = flow_control.FlowControl(
            settings=self._settings,
            write_record=self._write_record,
            forward_record=self._forward_record,
            recover_records=self._recover_records,
            **kwargs,
        )

    def _forward_record(self, record: "Record") -> None:
        self._context_keeper.add_from_record(record)
        tracelog.log_message_queue(record, self._sender_q)
        # print("FORWARD1", record)
        self._sender_q.put(record)

    def _write_record(self, record: "Record") -> int:
        # print("WRITE1", record)
        assert self._ds
        ret = self._ds.write(record)
        assert ret is not None

        (_start_offset, end_offset, flush_offset) = ret
        return end_offset

    def _ensure_flushed(self, offset: int) -> None:
        if self._ds:
            self._ds.ensure_flushed(offset)

    def _recover_records(self, start: int, end: int) -> None:
        record = pb.Record()
        request = pb.Request()
        # last_write_offset = self._track_last_written_offset
        sender_read = pb.SenderReadRequest(start_offset=start, end_offset=end)
        request.sender_read.CopyFrom(sender_read)
        record.request.CopyFrom(request)
        self._ensure_flushed(end)
        self._forward_record(record)
        # print("MARK", last_write_offset)

    def _write(self, record: "Record") -> None:
        if not self._ds:
            self.open()
        assert self._flow_control

        # temporarily support flow control being disabled (at first by default)
        if not self._settings._flow_control:
            self._write_record(record)
            self._forward_record(record)
            return

        # FlowControl will write data to disk and throttle sending to the sender
        self._flow_control.flow(record)

    def write(self, record: "Record") -> None:
        record_type = record.WhichOneof("record_type")
        assert record_type
        writer_str = "write_" + record_type
        write_handler: Callable[[Record], None] = getattr(self, writer_str, None)  # type: ignore
        if write_handler:
            return write_handler(record)
        # assert write_handler, f"unknown handle: {writer_str}"
        self._write(record)

    def write_request(self, record: "Record") -> None:
        request_type = record.request.WhichOneof("request_type")
        assert request_type
        write_request_str = "write_request_" + request_type
        write_request_handler: Callable[[Record], None] = getattr(self, write_request_str, None)  # type: ignore
        if write_request_handler:
            return write_request_handler(record)
        self._write(record)

    def write_request_sync_status(self, record: "Record") -> None:
        result = proto_util._result_from_record(record)
        if self._sender_status_report:
            result.response.sync_status_response.last_synced_time.CopyFrom(
                self._sender_status_report.last_synced_time
            )
        # todo: add logic to populate sync_status_response
        self._respond_result(result)

    def write_request_sender_status_report(self, record: "Record") -> None:
        self._sender_status_report = record.request.sender_status_report

    def write_request_cancel(self, record: "Record") -> None:
        cancel_id = record.request.cancel.cancel_slot
        self._context_keeper.cancel(cancel_id)

    def _respond_result(self, result: "Result") -> None:
        tracelog.log_message_queue(result, self._result_q)
        self._result_q.put(result)

    def finish(self) -> None:
        if self._ds:
            self._ds.close()
        if self._flow_control:
            self._flow_control.flush()
        self._context_keeper._debug_print_orphans()

    def debounce(self) -> None:
        pass
