import typing, logging, os, json
from moecolor import FormatText as ft
from datetime import datetime
from pathlib import Path

BASIC_LOGGING_FIELDS = {
    'log.level'   : '',  # 'Message log level, e.g. error, warning, timer, app_info. Automatically generated',
    '@timestamp'  : '',  # 'Timestamp in iso format, e.g 2023-02-17T23:16:41.220Z. Automatically generated',
    'message'     : ''   # 'Message containing log information, and the message format is: ' \
}

class ConsoleFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%', cfmt:str='', colors: str=[]):
        self.levels = {
            'DEBUG'     : ['yellow' , '#fff9ae'],
            'INFO'      : ['green'  , '#d3ffb3'],
            'WARNING'   : ['orange' , '#ffc100'],
            'TIMER'     : ['blue'   , '#71c7ec'],
            'ERROR'     : ['red'    , '#ba262b'],
            'CRITICAL'  : ['#8d0101', '#d5212e'],
            'APP_INFO'  : ['#5fd700', '#5fffaf']
        }
        if cfmt:
            # Default log message format
            self.colors = colors
            self.cfmt = True
            self.asctime = '[ '
            self.base_attr = f' {cfmt.upper()} '
        else:
            self.colors = []
            self.cfmt = False
            self.asctime = '[ ' + ft('%(asctime)s', color='purple').text
            self.base_attr = ' | %(name)s | %(funcName)s | LN%(lineno)d | %(levelname)s'
        self.message    = ' %(message)s'
        super().__init__(fmt=None, datefmt=None, style='%')

    def get_format(self, level, field: str=''):
        if self.cfmt:
            attr_format = self.base_attr
            colors = self.colors
        else:
            colors = self.levels.get(level, [])
            attr_format = f' | %({field})s' + self.base_attr if field else self.base_attr
        if colors:
            return self.asctime + ft(attr_format, colors[0]).text + ' ] ' + ft(self.message, colors[1]).text
        else:
            return self.asctime + attr_format + ' ] ' + self.message

    def format(self, record):
        _format = self.get_format(record.levelname, None)
        formatter = logging.Formatter(_format)
        return formatter.format(record)

class JSONFormatter(logging.Formatter):
    def __init__(self, logging_fields):
        self.logging_fields = logging_fields

    def format(self, record):
        message = f'[{record.name} | {record.funcName} | LN{record.lineno}]: {record.getMessage()}'
        date_time = datetime.fromtimestamp(record.created)
        isoformat = date_time.isoformat()[:-3] + 'Z'
        _logging_fields = {}
        _logging_fields['@timestamp']  = isoformat
        _logging_fields['log.level']   = record.levelname
        _logging_fields['message']     = message
        for key, value in self.logging_fields.items():
            if value:
                _logging_fields[key]  = getattr(record, value, '')
        return json.dumps(_logging_fields)

class ExtraAttributes(logging.Filter):
    def __init__(self, **params):
        self.extra_attr = params
        super().__init__()

    def filter(self, record):
        for key, value in self.extra_attr.items():
            record.__setattr__(key, value)
        return True

class MoeLogger:
    def __init__(self, json_format: bool=False, log_level: str='WARNING', logging_fields: typing.Dict={},
                 log_to_file: bool=False, max_bytes: int=3*1024*1024) -> None:
        self._ecs_fields     = {}
        self.json_format     = json_format
        self.level           = log_level.upper()
        self.max_bytes       = max_bytes
        self.log_to_file     = log_to_file
        self.file_handler    = None
        self.console_handler = logging.StreamHandler()
        self.logging_fields  = logging_fields
        self.configure_logging()
        self.setup_logger()

    @property
    def ecs_fields(self):
        return self._ecs_fields

    @ecs_fields.getter
    def ecs_fields(self):
        return self._ecs_fields

    @ecs_fields.setter
    def ecs_fields(self, key, value):
        self._ecs_fields[key] = value

    def _console_handler(self):
        self._console_formatter = JSONFormatter(self.logging_fields) if self.json_format else ConsoleFormatter()
        self.level = self.level if self.level in ['DEBUG', 'INFO', 'ERROR', 'WARN',
                                                  'WARNING', 'CRITICAL', 'FATAL'] else 'WARNING'
        self.console_handler.setFormatter(self._console_formatter)
        self.console_handler.setLevel(self.level)

    def _file_handler(self):
        ext = 'log'
        logs_dir = Path('logs')
        logs_dir.mkdir(exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d")
        log_file = os.path.join(logs_dir, f'{timestamp}.{ext}')
        # split file if it exists and greater than maxBytes
        if os.path.isfile(log_file) and os.path.getsize(log_file) > self.max_bytes:
            cnt = 1
            while True:
                log_file = os.path.join(logs_dir, f'{timestamp}.{cnt}.{ext}')
                if os.path.isfile(log_file):
                    cnt += 1
                else:
                    break
        # Rollover mechanism, does not work like we need...
        # RotatingFileHandler(log_file, maxBytes=maxBytes, backupCount=backupCount)
        file_format= {'@timestamp': '%(asctime)s', 'app.name': '%(app_name)s', 'log.level': '%(levelname)s',
                      'message': '[%(name)s | %(funcName)s | LN%(lineno)d]: %(message)s'}
        file_format = json.dumps(file_format, indent=4, separators=(",", ":"))
        file_formatter = logging.Formatter(file_format)
        self.file_handler = logging.FileHandler(log_file, mode='a+')
        self.file_handler.setFormatter(file_formatter)
        self.file_handler.setLevel(logging.WARNING)

    def _add_filter(self, **kwargs):
        _filter = ExtraAttributes(**kwargs)
        self.console_handler.addFilter(_filter)
        if self.file_handler:
            self.file_handler.addFilter(_filter)

    def _update_filter(self, **kwargs):
        # If filter exits -> update value, otherwise create new one
        add_filter = True
        field, value = tuple(kwargs.items())[0]
        for _filter in self.console_handler.filters:
            if _filter.extra_attr.get(field, None) is not None:
                # Update with new value
                _filter.extra_attr[field] = value
                add_filter = False
                break
        # Add new filter if necessary...
        if add_filter:
            self._add_filter(**kwargs)

    def setup_logger(self):
        # Universal setup for logger...
        logging.basicConfig(handlers=[self.console_handler] if not self.file_handler else
                            [self.file_handler, self.console_handler], level=self.level)

    def configure_logging(self):
        MoeLogger.addLoggingLevel('TIMER', logging.CRITICAL + 5)
        MoeLogger.addLoggingLevel('APP_INFO', logging.CRITICAL + 6)
        logging.Formatter.default_msec_format = '%s.%03dZ'
        logging.Formatter.default_time_format = "%Y-%m-%dT%H:%M:%S" # Setup iso8601 format
        if self.log_to_file:
            self._file_handler()
        self._console_handler()

    def update_filter(self, **kwargs):
        self._update_filter(**kwargs)

    @staticmethod
    def addLoggingLevel(levelName, levelNum, methodName=None):
        """
        Adapted from: https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility
        Example
        -------
        >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
        >>> logging.getLogger(__name__).setLevel("TRACE")
        >>> logging.trace('log message')

        """
        if not methodName:
            methodName = levelName.lower()

        if hasattr(logging, levelName):
            logging.debug('{} already defined in logging module'.format(levelName))
            return False
        if hasattr(logging, methodName):
            logging.debug('{} already defined in logging module'.format(levelName))
            return False
        if hasattr(logging.getLoggerClass(), methodName):
            logging.debug('{} already defined in logger class'.format(methodName))
            return False

        def logForLevel(self, message, *args, **kwargs):
            if self.isEnabledFor(levelNum):
                self._log(levelNum, message, args, **kwargs)
        def logToRoot(message, *args, **kwargs):
            logging.log(levelNum, message, *args, **kwargs)

        logging.addLevelName(levelNum, levelName)
        setattr(logging, levelName, levelNum)
        setattr(logging.getLoggerClass(), methodName, logForLevel)
        setattr(logging, methodName, logToRoot)
        return True


# def _update_logger(self):
#     """Helper function to update logger parameters
#     """
#     for field in self._attributes:
#         value = getattr(AdcAttributes, field)
#         # Update field only if it is different and part of the ecs schema...
#         if field in AC.LOGGING_FIELDS.values() and self._logger.ecs_fields.get(field, None) != value:
#             self._logger.update_filter(**{field: value})
#             self._logger.setup_logger()

def quick_logger_setup():
    logger = MoeLogger(False, 'INFO')
    logger.setup_logger()

def moelogger(msg: str, cfmt: str='', colors=[]):
    quick_logger_setup()