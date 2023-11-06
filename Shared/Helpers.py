import os, logging, traceback, argparse, inspect

DEFAULT_LOGGING_LVL = 'INFO'
def initLogging(logFilename, progName=None):
	parser = argparse.ArgumentParser(progName)
	parser.add_argument('--log', help='set the logging level', type=str, default=DEFAULT_LOGGING_LVL)
	logLvl = parser.parse_args().log
	logLvl = getattr(logging, logLvl.upper(), DEFAULT_LOGGING_LVL)
	if not os.path.exists('logs'): os.mkdir('logs')
	logging.basicConfig(filename=os.path.join('logs', logFilename), level=logLvl, format='[%(levelname)s] %(asctime)s %(process)d:%(threadName)s:%(module)s:%(funcName)s:    %(message)s')
	logging.debug('running')
def asert(cond, msg, obj=None):
	if cond: return
	if obj is not None:
		msg = f"{msg}: '{obj}'"
	caller = inspect.getframeinfo(inspect.stack()[1][0])
	msg = f'{os.path.basename(caller.filename)}:{caller.lineno} ASSERTION FAILED: {msg}'
	logging.error(msg)
	exit(msg)
def runFuncLogged(func):
	try:
		func()
	except Exception as e:
		strs = traceback.format_exception(type(e), e, e.__traceback__)
		strs = 'UNCATCHED ' + strs[-1] + ''.join(['	' + s for s in strs[:-1]])
		logging.critical(strs)
		raise
