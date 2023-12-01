import logging
from moelog import quick_logger_setup

logger = logging.getLogger(__name__)
quick_logger_setup()

logger.info("This text is GREEN")
print("ok")