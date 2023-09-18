"""socket service.

Implement ServiceInterface for socket transport.
"""

from typing import TYPE_CHECKING, Optional

from wandb.proto import wandb_internal_pb2 as pb
from wandb.proto import wandb_server_pb2 as spb

from ..lib.sock_client import SockClient
from .service_base import ServiceInterface

if TYPE_CHECKING:
    from wandb.sdk.wandb_settings import Settings


class ServiceSockInterface(ServiceInterface):
    _sock_client: SockClient

    def __init__(self) -> None:
        self._sock_client = SockClient()

    def get_transport(self) -> str:
        return "tcp"

    def _get_sock_client(self) -> SockClient:
        return self._sock_client

    def _svc_connect(self, port: int) -> None:
        self._sock_client.connect(port=port)

    def _svc_inform_init(self, settings: "Settings", run_id: str) -> None:
        inform_init = spb.ServerInformInitRequest()
        inform_init.settings.CopyFrom(settings.to_proto())
        inform_init._info.stream_id = run_id
        assert self._sock_client
        self._sock_client.send(inform_init=inform_init)

    def _svc_inform_start(self, settings: "Settings", run_id: str) -> None:
        inform_start = spb.ServerInformStartRequest()
        inform_start.settings.CopyFrom(settings.to_proto())
        inform_start._info.stream_id = run_id
        assert self._sock_client
        self._sock_client.send(inform_start=inform_start)

    def _svc_inform_finish(self, run_id: Optional[str] = None) -> None:
        assert run_id
        inform_finish = spb.ServerInformFinishRequest()
        inform_finish._info.stream_id = run_id

        assert self._sock_client
        self._sock_client.send(inform_finish=inform_finish)

    def _svc_inform_attach(self, attach_id: str) -> spb.ServerInformAttachResponse:
        inform_attach = spb.ServerInformAttachRequest()
        inform_attach._info.stream_id = attach_id

        assert self._sock_client
        response = self._sock_client.send_and_recv(inform_attach=inform_attach)
        return response.inform_attach_response

    def _svc_notify_loop(self) -> None:
        while True:
            response = self._sock_client.read_server_response(timeout=1)
            print("GOT", response)

    def _svc_inform_teardown(self, exit_code: int) -> None:
        inform_teardown = spb.ServerInformTeardownRequest(exit_code=exit_code)

        assert self._sock_client
        self._sock_client.send(inform_teardown=inform_teardown)

    def _svc_inform_broadcast(self, record: pb.Record, subscription_key: str) -> None:
        inform_broadcast = spb.ServerInformBroadcastRequest(
            record=record,
            subscription_key=subscription_key,
        )

        assert self._sock_client
        self._sock_client.send(inform_broadcast=inform_broadcast)

    def _svc_inform_subscribe(self, run_id: str, subscription_key: str) -> None:
        inform_subscribe = spb.ServerInformSubscribeRequest(
            run_id=run_id, subscription_key=subscription_key
        )

        assert self._sock_client
        self._sock_client.send(inform_subscribe=inform_subscribe)

    def _svc_inform_unsubscribe(self, run_id: str, subscription_key: str) -> None:
        inform_unsubscribe = spb.ServerInformUnsubscribeRequest(
            run_id=run_id, subscription_key=subscription_key
        )

        assert self._sock_client
        self._sock_client.send(inform_unsubscribe=inform_unsubscribe)

    def _svc_notify_read(self) -> None:
        assert self._sock_client
        response = self._sock_client.read_server_response(timeout=1)
        return response
