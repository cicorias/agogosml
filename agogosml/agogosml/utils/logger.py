"""Logger."""
import logging
import logging.config
import os
from pathlib import Path
from typing import Dict
from typing import Optional
from typing import Union

import yaml
from applicationinsights import TelemetryClient
from applicationinsights.channel import AsynchronousQueue
from applicationinsights.channel import AsynchronousSender
from applicationinsights.channel import TelemetryChannel
from applicationinsights.channel import TelemetryContext
from cached_property import cached_property
from singleton_decorator import singleton


class NullTelemetryClient:
    """Null-object implementation of the TelemetryClient."""

    def __init__(self):
        """Null-object implementation of the TelemetryClient."""

    def track_trace(self, name, properties=None, severity=None):
        """Do nothing."""

    def track_event(self, name, properties=None, measurements=None):
        """Do nothing."""


@singleton
class Logger:
    """Logger."""

    def __init__(self,
                 name: str = __name__,
                 path: str = 'logging.yaml',
                 env_key: str = 'LOG_CFG',
                 level: int = logging.INFO):
        """Implement trace and event logging functionality."""
        self.level = level
        self.name = name
        self.path = path
        self.env_key = env_key
        self.ikey = os.getenv('APPINSIGHTS_INSTRUMENTATIONKEY')
        self.endpoint = os.getenv('APPINSIGHTS_ENDPOINT')

    @cached_property
    def _logger(self) -> logging.Logger:
        """Create the logger."""
        value = os.getenv(self.env_key)
        path = Path(value or self.path)

        if path.is_file():
            with path.open('rt') as fobj:
                config = yaml.safe_load(fobj.read())
            logging.config.dictConfig(config)
        else:
            logging.basicConfig(
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                level=self.level)

        return logging.getLogger(self.name)

    @cached_property
    def _telemetry(self) -> Union[TelemetryClient, NullTelemetryClient]:
        """Create the telemetry client."""
        if not self.ikey:
            return NullTelemetryClient()

        if self.endpoint:
            sender = AsynchronousSender(self.endpoint)
        else:
            sender = AsynchronousSender()
        queue = AsynchronousQueue(sender)
        context = TelemetryContext()
        context.instrumentation_key = self.ikey
        channel = TelemetryChannel(context, queue)
        return TelemetryClient(self.ikey, telemetry_channel=channel)

    def debug(self, message: str, *args):
        """Log debug message."""
        self._log(logging.DEBUG, message, *args)

    def info(self, message: str, *args):
        """Log info message."""
        self._log(logging.INFO, message, *args)

    def error(self, message: str, *args):
        """Log error message."""
        self._log(logging.ERROR, message, *args)

    def event(self, name: str, props: Optional[Dict[str, str]] = None):
        """Log an event."""
        props = props or {}
        self._logger.info('Event %s: %r', name, props)
        self._telemetry.track_event(name, props)

    def _log(self, level: int, message: str, *args):
        """Log a message."""
        if not self._logger.isEnabledFor(level):
            return

        self._logger.log(level, message, *args)
        self._telemetry.track_trace(
            message, severity=logging.getLevelName(level))
