import os, sys
import logging, traceback, argparse

# logging ------------------------------
DEFAULT_LOGGING_LVL = 'INFO'
def initLogging(logFilename, progName=None):
	parser = argparse.ArgumentParser(progName)
	parser.add_argument('--log', help='set the logging level', type=str, default=DEFAULT_LOGGING_LVL)
	args, unknown = parser.parse_known_args()
	logLvl = getattr(logging, args.log.upper(), DEFAULT_LOGGING_LVL)
	if not os.path.exists('logs'): os.mkdir('logs')
	handlers = [logging.FileHandler(os.path.join('logs', logFilename)), logging.StreamHandler()]
	handlers[1].setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
	logging.basicConfig(handlers=handlers, level=logLvl, format='[%(levelname)s] %(asctime)s %(process)d:%(threadName)s:%(module)s:%(funcName)s:	%(message)s')
	logging.debug('running')
def runFuncLogged(func):
	try:
		func()
	except Exception as e: # NOTE does not catch KeyboardInterrupt
		strs = traceback.format_exception(type(e), e, e.__traceback__)
		err = strs[-1]
		strs = 'UNCATCHED ' + err + ''.join(['	' + s for s in strs[:-1]])
		logging.critical(strs)
		print(err, end='')
		raise SystemExit()
