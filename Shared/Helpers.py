import logging, traceback

def runFuncLogged(func):
	try:
		func()
	except Exception as e:
		strs = traceback.format_exception(type(e), e, e.__traceback__)
		strs = 'UNCATCHED ' + strs[-1] + ''.join(['	' + s for s in strs[:-1]])
		logging.critical(strs)
		raise
