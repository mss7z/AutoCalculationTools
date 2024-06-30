import glob
import os
import threading
import multiprocessing
import subprocess
import datetime
import time
import paramiko
import stat
import queue
import math
from dataclasses import dataclass
import json

basePath=os.getcwd()


print("hello runRunfeko")

class Logger:
	"""ログファイルの生成を行うクラスです"""
	logDirStd=os.path.join(basePath,"runRunfekoLogs")
	def __init__(self,filename="nanashi",filedir=None,filenamePrefix=""):
		if filedir==None:
			if not os.path.isdir(self.logDirStd):
				os.makedirs(self.logDirStd)
			self.logDir=self.logDirStd
		else:
			self.logDir=filedir
		self.timeStr=datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
		self.filename=filename
		self.filenamePrefix=filenamePrefix
	def append(self,s):
		"""ログファイルに追加します"""
		self.f.write(datetime.datetime.now().strftime("[%Y%m%d_%H%M%S] ")+s)
	def appendln(self,s):
		"""ログファイルに改行付きで追加します"""
		self.append(s+"\n")
	def open(self):
		"""ログファイルを開きます"""
		self.f=open(os.path.join(self.logDir,
			self.filenamePrefix+self.timeStr+self.filename+".txt"),"a")
	# with構文を使うときに使います
	def __enter__(self):
		self.open()
		return self
	def __exit__(self,exc_type, exc_value, traceback):
		#print("kesitawo")
		self.close()
	def close(self):
		"""ログファイルを閉じます"""
		self.f.close()
	@classmethod
	def paramikoLogSetting(cls):
		"""paramikoのログを格納します
		classmethodとしてここに入れなくてもよかったかも"""
		if not os.path.isdir(cls.logDirStd):
			os.makedirs(cls.logDirStd)
		timeStr=datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
		paramiko.util.log_to_file(os.path.join(cls.logDirStd,timeStr+"paramiko.txt"))

class InterruptUserInterface:
	"""割り込みしてユーザのコマンドを受け取るためのクラスです
	スレッドである必要があります"""
	def __init__(self):
		self.inputQueue=queue.Queue()
		self.lock=threading.Lock() 
		self.ui=threading.Thread(target=self.userInterface)
		self.ui.daemon=True
		self.ui.start()
	def userInterface(self):
		"""スレッドでコールされるプライベートな関数です"""
		while True:
			s=input()
			self.lock.acquire()
			self.inputQueue.put(s)
			self.lock.release()
			print(f"コマンド{s}を受け付けました")
	def isExist(self):
		"""入力されたコマンドが存在するかどうかを調べます"""
		return not self.inputQueue.empty()
	def get(self):
		"""入力されたコマンドを取得します"""
		if not self.inputQueue.empty():
			return self.inputQueue.get()
		else:
			return None

class SolverManager:
	def __init__(self,solvers):
		self.solvers=solvers
	def getSolvers(self):
		"""ソルバーを得ます"""
		if self.getRunningSolverNum()>=20:
			#print("ライセンス不足")
			return []
		retSol=[x for x in self.solvers if x.askCanCalc()]
		# for sol in self.solvers:
			# if sol.askCanCalc():
				# retSol=sol
				# break
		return retSol
	def waitSolvers(self):
		"""すべてのソルバーが完了するのを待ちます"""
		for sol in self.solvers:
			sol.waitJob()
	def isAllSolversDoneJob(self):
		"""すべてのソルバーが完了したかどうかを返します"""
		for sol in self.solvers:
			if sol.isRunning():
				return False
		return True
	def stopSolvers(self):
		"""すべてのソルバーを中断します"""
		for sol in self.solvers:
			sol.requestStop()
	def getRunningSolverNum(self):
		"""現在実行中のソルバーの数を返します"""
		num=0
		for sol in self.solvers:
			if sol.isRunning():
				num+=1
		return num
	def getRunningJobs(self):
		"""現在実行中のソルバーを返します"""
		ret=[sol.getRunningName() for sol in self.solvers if sol.isRunning()]
		#print(ret)
		return ret
	def check(self):
		for sol in self.solvers:
			sol.check()
	def getStatus(self):
		return {"sols":{
			x.getName():x.getStatus() for x in self.solvers
		}}
	def setStatus(self,x):
		for name,status in x["sols"].items():
			for sol in self.solvers:
				if sol.getName()==name:
					sol.setStatus(status)

class Stopwatch:
	"""ストップウォッチです
	時間計測に使用しています"""
	def __init__(self):
		self.start()
	def start(self):
		self.startT=time.time()
		self.stopT=self.startT
	def stop(self):
		self.stopT=time.time()
	def getSec(self):
		return self.stopT-self.startT
	def getStr(self):
		td=datetime.timedelta(seconds=self.getSec())
		return str(td)
	def getStop(self):
		return self.stopT
	def checkSec(self):
		return time.time()-self.startT


class HostManager:
	"""ホストの代理人です"""
	class SSHConnection:
		"""paramikoのSSHとSFTPの接続をセットで行うクラスです"""
		def __init__(self,client,sftp,motherManager):
			self.client=client
			self.sftp=sftp
			self.motherManager=motherManager
		def getClientAndSftp(self):
			return self.client,self.sftp
		def close(self):
			self.sftp.close()
			self.client.close()
			self.motherManager._endSSHconnection()
	def __init__(self,username,password,hostname,logname,port=22,parallelRunningMax=1):
		self.logger=Logger(f"host_{logname}")
		self.username=username
		self.password=password
		self.hostname=hostname
		self.port=port
		self.runningContMem=multiprocessing.Value("i",0)
		self.parallelRunningMax=parallelRunningMax
		
	def askCanCalc(self):
		"""ホストが計算可能であるかを返します"""
		if self.runningContMem.value<self.parallelRunningMax:
			return True
		else:
			return False
	
	def getSSHconnection(self):
		"""ホストの接続を返します
		その際にclass SSHConnectionで返します"""
		try:
			client=paramiko.SSHClient()
			client.load_system_host_keys()
			client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			client.connect(hostname=self.hostname,username=self.username,port=self.port,password=self.password,timeout=100)
			sftp=client.open_sftp()
			with self.logger as log:
				log.appendln(f"success to connect")
			self.runningContMem.value+=1
			return self.SSHConnection(client,sftp,self)
		except Exception as e:
			with self.logger as log:
				log.appendln(f"failed to connect due to {e}")
			print("getSSHconnection end")
			if "sftp" in locals():
				sftp.close()
			if "client" in locals():
				client.close()
		return None
	
	def _endSSHconnection(self):
		self.runningContMem.value-=1
	
	def __str__(self):
		return f"{self.username}@{self.hostname}"

class CalcFinishTime:
	def __init__(self):
		self.totalPercent=0
		self.totalTime=0
		
		#確定していない分
		self.appendPercent=0
		self.appendTime=0
	def getCompleteSec(self):
		currentPercent=self.appendPercent+self.totalPercent
		if currentPercent==0:
			return None
	
		timePerPercent=(self.totalTime+self.appendTime)/currentPercent
		return timePerPercent*100
	def setNowPercentAndSec(self,p,s):
		self.appendPercent=p
		self.appendTime=s
	def beSettled(self):
		self.totalPercent+=self.appendPercent
		self.totalTime+=self.appendTime
	def getStatus(self):
		if self.totalPercent!=0:
			aveSecPerOne=(self.totalTime*100)/self.totalPercent
		else:
			aveSecPerOne=None
		return {
			"percent":self.totalPercent,
			"sec":self.totalTime,
			"_aveSecPerOne":aveSecPerOne
		}
	def setStatus(self,x):
		self.totalPercent=x["percent"]
		self.totalTime=x["sec"]
class SolverViaSSH:
	"""SSHを経由したソルバーの代理人です"""
	@dataclass
	class _ToProcessPack:
		cmd:str
		logname:str
		host:HostManager
	def __init__(self,cmd,host,logname,costs,costMult=1.0):
		self.cmd=cmd
		self.logname=logname
		self.isRunningVal=False
		self.errorcodeCont=0
		
		self.canCalcTime=0
		self.host=host
		self.costs={key:cost*costMult for key,cost in costs.items()}
		
		self.currentRunningName=""
		self.toProcess=None
		
		self.toProcessPack=self._ToProcessPack(
			cmd=cmd,
			logname=logname,
			host=host
		)
		
		self.calcFinishTime={}
	def getName(self):
		return f"logname_{self.logname}"
	def getStatus(self):
		return {"cft":{
			key:cft.getStatus() for key,cft in self.calcFinishTime.items()
		}}
	def setStatus(self,x):
		for key,v in x["cft"].items():
			if not key in self.calcFinishTime:
				self.calcFinishTime[key]=CalcFinishTime()
			self.calcFinishTime[key].setStatus(v)
	def askCanCalc(self):
		"""ソルバーが計算可能であるかどうかを返します"""
		if not self.host.askCanCalc():
			return False
		if self.canCalcTime<time.time():
			#計算できるとき
			self.canCalcTime=0
		else:
			return False
		if self.errorcodeCont>2:
			self.errorcodeCont=0
			#後に再び計算を試みる
			self.canCalcTime=time.time()+120
			return False
		return not bool(self.isRunningVal)
	def askCalcCost(self,job):
		"""計算コストがいくらになるかを見積もります"""
		keywords=job.getInfo("costKeywords")
		for cost in self.costs:
			if cost in keywords:
				#print(f"{name}は{self.costs[cost]}で計算可能")
				return self.costs[cost]
		else:
			return math.inf
	def askCalcSec(self,job):
		timeType=job.getInfo("timeType")
		if timeType in self.calcFinishTime:
			return self.calcFinishTime[timeType].getCompleteSec()
		else:
			return None
		
	@staticmethod
	def jobCore(name,toMother,pack):
		"""multiprocessingで呼び出されるSSHとSFTPによる通信シーケンスのコアです"""
		print("call job core")
		
		localCd=os.path.join(basePath,name)
		print("run dir:",localCd)
		os.chdir(localCd)
		
		# fileName=os.path.splitext(glob.glob("*.cfs")[0])[0]
		actCmd=pack.cmd#.format(fileName)
		#actCmd=f"sleep 30 && echo {name}"
		print("actCmd:",actCmd)
		
		stopwatch=Stopwatch()
		timeoutStopwatch=Stopwatch()
		logger=Logger(
			filenamePrefix="0rm_",
			filename=f"job_{pack.logname}_{name}_NOUP",
			filedir=os.getcwd()
		)
		isSuccessCalc=True
		calcStatus="unknown_err"
		try:
			#https://self-development.info/python%E3%81%A7paramiko%E3%81%AB%E3%82%88%E3%82%8B%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB%E8%BB%A2%E9%80%81%E3%80%90no%EF%BC%81scp%E3%80%91/
			
			# 接続を開始します
			sshConnection=pack.host.getSSHconnection()
			if sshConnection==None:
				raise RuntimeError("sshConnectionを開始できません")
				
			client,sftp=sshConnection.getClientAndSftp()
			
			# リモート一時ディレクトリを生成します
			remoteCd=datetime.datetime.now().strftime("%Y%m%d_%H%M%S_runRunfeko_tmp")
			print(f"リモート一時ディレクトリ {remoteCd}")
			
			sftp.mkdir(remoteCd)
			sftp.chdir(remoteCd)
			
			# リモート一時ディレクトリにファイルを転送します
			localToRemoteFiles=[x for x in glob.glob("*") if os.path.isfile(x)]
			for file in localToRemoteFiles:
				if "NOUP" in file:
					continue
				sftp.put(file,file)
				print(file)
			print("ファイル転送完了")
			
			# 計算を開始します
			stopwatch.start()
			timeoutStopwatch.start()
			stdin,stdout,stderr = client.exec_command(f"cd {remoteCd} && {actCmd}",get_pty=True)
			#stdin,stdout,stderr = client.exec_command("sleep 5 && echo stderr >&2")
			stdout.channel.set_combine_stderr(True)
			print("out exec")
			print("type stdout",type(stdout))
			
			# SSHで送られてくる標準出力と標準エラー出力をLoggerを用いて保存する際に、メインループがブロックするのを防ぐためにスレッド化しています
			# これによってタイムアウトを検出できます
			#https://stackoverflow.com/questions/375427/a-non-blocking-read-on-a-subprocess-pipe-in-python
			stdoutQueue=queue.Queue()
			def watchStdout():
				while True:
					line=stdout.readline()
					if line:
						stdoutQueue.put(line.replace("\n",""))
					else:
						break
					print("*",end="",flush=True)
			stdoutWatcher=threading.Thread(target=watchStdout)
			stdoutWatcher.daemon=True
			stdoutWatcher.start()
			
			percentStartStr="@percent:"
			percentOffset=len(percentStartStr)
			while True:
				# 標準出力のキューにデータがあればloggerで保存します
				if not stdoutQueue.empty():
					line=stdoutQueue.get()
					startIndex=line.find(percentStartStr)
					if startIndex!=-1:
						p=float(line[startIndex+percentOffset:].split("%")[0])
						toMother.send({"type":"percent","val":p,"sec":stopwatch.checkSec()})
					with logger as log:
						#log.append(f"returncode:{process.returncode}")
						log.append(line)
					timeoutStopwatch.start()
				# リモート上で実行が完了したら…
				elif stdout.channel.exit_status_ready():
					stopwatch.stop()
					print("リモート上でのcmdの実行が完了しました",end="")
					errorcode=stdout.channel.recv_exit_status()
					with logger as log:
						log.appendln(f"@:errorcode:{errorcode}")
						log.appendln(f"@:seconds:{stopwatch.getSec()}")
						log.appendln(f"@:time:{stopwatch.getStr()}")
						log.appendln(f"@:endTime:{stopwatch.getStop()}")
						log.appendln(f"@:name:{name}")
						log.appendln(f"@:localCd:{localCd}")
						log.appendln(f"@:remoteCd:{remoteCd}")
						log.appendln(f"@:cmd:{actCmd}")
						
					if errorcode!=0:
						isSuccessCalc=False
						
					print(f"errorcode:{errorcode}")
					break
				# SolverManagerからctrl-cで終了するようにフラグが建てられたら終了します
				if toMother.poll():
					msg=toMother.recv()
					type_=msg["type"]
					if type_=="stop":
						#https://progrunner.hatenablog.jp/entry/2020/12/18/124259
						print("\x03", file=stdin, end="")
						print(f"{pack.host}にCtrl-Cを送出しました")
						isSuccessCalc=False
					elif type_=="logmsg":
						with logger as log:
							log.appendln(f"@:msg:{msg['str']}")
				# SSHConnectionがタイムアウトしているかをチェックします
				if timeoutStopwatch.checkSec()>3600:
					print("sshコネクションにエラーが発生した模様です")
					isSuccessCalc=False
					break
				time.sleep(0.01)
			
			time.sleep(1)
			
			# リモート一時ディレクトリのファイル一覧を取得します
			remoteToLocalList=sftp.listdir_attr()
			
			# .outファイルがなければ失敗と判断します
			if not f"0rm_doneFlagFile" in [x.filename for x in remoteToLocalList]:
				print(f"0rm_doneFlagFileがないため失敗と推測")
				isSuccessCalc=False
			
			# リモート一時ディレクトリからダウンロードします
			# 計算に失敗していると判断できる際にはそこでリモート上のファイルを削除して完了します
			# print(remoteToLocalList)
			for file in remoteToLocalList:
				fname=file.filename
				if stat.S_ISREG(file.st_mode):
					if "NODOWN" in fname:
						print("不要",end="")
					else:
						if isSuccessCalc:
							sftp.get(fname,fname)
							print("受信",end="")
						else:
							print("破棄",end="")
					sftp.remove(fname)
					print(fname)
				elif stat.S_ISDIR(file.st_mode):
					sftp.rmdir(fname)
			print("ファイル終了処理完了")
			
			# リモート一時ディレクトリを削除します
			sftp.chdir("..")
			sftp.rmdir(remoteCd)
			with logger as log:
				log.appendln("@:msg: success func jobCore")
		except Exception as e:
			print("例外発生")
			print(e)
			with logger as log:
				log.appendln(f"@:msg: failed func jobCore {e}")
			isSuccessCalc=False
		finally:
			if sshConnection!=None:
				sshConnection.close()
		
		with logger as log:
			log.appendln("@:logVer:11")
			log.appendln("@:logEnd:")
		
		if isSuccessCalc:
			calcStatus="success"
			toMother.send({"type":"percent","val":100.0,"sec":stopwatch.getSec()})
		
		toMother.send({"type":"end","status":calcStatus})
		
		while True:
			msg=toMother.recv()
			if msg["type"]=="endOk":
				break
		print("end cmd")
		
	def calc(self,job):
		"""メインプロセスのメインスレッド上で計算の命令を受け付けます"""
		print("call calc ")
		self.job=job
		name=job.getName()
		if not self.askCanCalc():
			print("internal error! askCanCalc()==False で calc() がコールされた")
			return
		#self.job=threading.Thread(target=jobCore)
		self.currentRunningName=name
		self.isRunningVal=True
		
		self.toProcess,toMother=multiprocessing.Pipe()
		self.jobProcess=multiprocessing.Process(target=self.jobCore,args=(name,toMother,self.toProcessPack))
		self.jobProcess.start()
		self.job.appendNowCalcingSolver(self)
		
		timeType=self.job.getInfo("timeType")
		if not timeType in self.calcFinishTime:
			self.calcFinishTime[timeType]=CalcFinishTime()
		self.currentFinishTimeInst=self.calcFinishTime[timeType]
		print("end calc ")
	def __checkMsg(self,msg):
		type_=msg["type"]
		# 計算が成功したかどうかのカウントをインクリメントまたはデクリメントします
		if type_=="end":
			# 計算中であることを示すフラグを折ります
			self.isRunningVal=False
			self.job.deleteNowCalcingSolver(self)
			status=msg["status"]
			if status=="success":
				if self.errorcodeCont>0:
					self.errorcodeCont-=1
				#他が計算する必要はもうないので止める
				self.job.requestStopAllCalcingSolver()
			else:
				self.errorcodeCont+=1
			# self.currentFinishTimeInst.setNowPercentAndSec(
				# p=100.0,s=msg["sec"]
			# )
			self.currentFinishTimeInst.beSettled()
			
			self.toProcess.send({"type":"endOk"})
			self.toProcess.close()
			self.toProcess=None
		elif type_=="percent":
			self.currentFinishTimeInst.setNowPercentAndSec(
				p=msg["val"],s=msg["sec"]
			)
			self.toProcess.send({
				"type":"logmsg",
				"str":f"estimate completeSec={self.currentFinishTimeInst.getCompleteSec()},"
			})
		else:
			raise ValueError(f"プロセスからの不明なメッセージ {msg}")
	def check(self):
		if self.toProcess!=None:
			if self.toProcess.poll():
				msg=self.toProcess.recv()
				self.__checkMsg(msg)
				
	def waitJob(self):
		"""計算が完了するのを待ちます"""
		while True:
			self.check()
			if not self.isRunningVal:
				break
			time.sleep(0.01)
		self.job.join()
	def requestStop(self):
		"""計算を終了します"""
		if self.toProcess!=None:
			self.toProcess.send({"type":"stop"})
			print("@SolverViaSSH requestStop フラグが立ちました")
	def isRunning(self):
		"""計算が実行しているかどうかを返しまします"""
		return self.isRunningVal
	def getRunningName(self):
		"""現在実行中または前回実行したモデル名を取得します"""
		return self.currentRunningName
	

class Job:
	def __init__(self,dirName):
		self.name=dirName
		self.statusDict={
			"failedCont":0,
		}
		self.nowCalcingSolverSet=set()
		
		self.jobInfo={
			"timeType":"default",
			"costKeywords":["fdtd",]
		}
		self.reloadFile()
	def reloadFile(self):
		self.__readJobInfo()
	def __readJobInfo(self):
		with open(os.path.join(self.name,"0rm_jobInfo.json"),mode="r") as f:
			print(self.name)
			self.jobInfo.update(json.load(f))
	def getInfo(self,key):
		return self.jobInfo[key]
	def getName(self):
		return self.name
	def isDone(self):
		return len(glob.glob(f"{self.name}/0rm_doneFlagFile"))!=0
	# def isWantToCalc(self):
		# if self.isNowCalcing:
			# return False
		# elif self.isDone():
			# return False
		# elif self.getFailedCont()>=2:
			# return False
		# return True
	def incrementFailedCont(self):
		self.statusDict["failedCont"]+=1
	def getFailedCont(self):
		return self.statusDict["failedCont"]
	# def updateStatus(self):
		# if self.isNowCalcing:
			# if self.isDone():
				# self.isNowCalcing=False
	def appendNowCalcingSolver(self,solver):
		self.nowCalcingSolverSet.add(solver)
	def deleteNowCalcingSolver(self,solver):
		self.nowCalcingSolverSet.remove(solver)
	def requestStopAllCalcingSolver(self):
		for solver in self.nowCalcingSolverSet:
			solver.requestStop()
	def getNowCalcingCont(self):
		return len(self.nowCalcingSolverSet)

class JobManager:
	"""ローカルのディレクトリからジョブ（モデル）の一覧を取得して管理します"""
	def __init__(self):
		self.jobDict={}
		self.reloadDir()
	
	"""def reloadDir(self,diff=[]):
		"ローカルのディレクトリを再読み込みします"
		def getCalcTarget():
			retTargets=[]
			targets=glob.glob("*/jobInfo.json")
			for target in targets:
				name=os.path.dirname(target)
				# print(name,end="...")
				if self.isDoneJobFromFile(name):
					# print("end")
					# retTargets.append(name)
					pass
				else:
					# print("MADA!")
					retTargets.append(name)
			return retTargets
		# self.nameList=getCalcTarget()
		self.jobList=[Job(name) for name in getCalcTarget() if not name in diff]
		# print(f"self.nameList {self.nameList}")
		return len(self.jobList)"""
	def reloadDir(self):
		currentDirJobNames=set([os.path.dirname(d) for d in glob.glob("*/0rm_jobInfo.json")])
		knownJobNames=set(self.jobDict.keys())
		
		#ディレクトリにはあるが、既知でないjob
		haveToAddJobNames=currentDirJobNames-knownJobNames
		for newName in haveToAddJobNames:
			self.jobDict[newName]=Job(newName)
			
		#既知だが、ディレクトリからなくなっているjob
		haveToDeleteJobNames=knownJobNames-currentDirJobNames
		for delName in haveToDeleteJobNames:
			targetJob=self.jobDict.pop(delName)
			targetJob.requestStopAllCalcingSolver()
		
		# for jobName in currentDirJobNames:
			# if not jobName in self.jobDict:
				# self.jobDict[jobName]=Job(jobName)
	
		# for d in glob.glob("*/0rm_jobInfo.json"):
			# jobName=os.path.dirname(d)
			# if not jobName in self.jobDict:
				# self.jobDict[jobName]=Job(jobName)
		# for job in self.jobDict.values():
			# job.updateStatus()
	# def next(self):
		# """次のジョブを取得します"""
		# while True:
			# if len(self.nameList)==0:
				# return None
			# ret=self.nameList.pop()
			# if not self.isDoneJobFromFile(ret):
				# break
		# return ret
	def getJobs(self):
		"""まだ計算が完了していないすべてのジョブを取得します"""
		return [job for job in self.jobDict.values() if not job.isDone()]
	def getJobCont(self):
		"""まだ計算が完了していないすべてのジョブの数を取得します"""
		return len(self.getJobs())

class MatchingEngine:
	def __init__(self,jobManager,solverManager):
		self.log=Logger("matchingEngine")
		self.jobManager=jobManager
		self.solverManager=solverManager
		
	def check(self):
		sols=self.solverManager.getSolvers()
		self.jobManager.reloadDir()#solverManager.getRunningJobs()+failedJobs)
		jobs=self.jobManager.getJobs()
		
		if len(jobs)==0:
			print("c",end="",flush=True)
		
		elif len(sols)!=0:
			#ソルバーに空きがあるとき
			
			#同時計算数が最小の者たちだけを残す
			nowCalcingList=[j.getNowCalcingCont() for j in jobs]
			nowCalcingMin=min(nowCalcingList)
			jobs=[j for j in jobs if j.getNowCalcingCont()==nowCalcingMin]
			
			def getBestPairByDeadline():
				# コストをすべて計算
				costList=[]
				for job in jobs:
					for sol in sols:
						candidate=sol.askCalcSec(job)
						if candidate==None:
							return None
						costList.append((candidate,sol,job))
				# 最小コストのものを選択
				return min(costList,key=lambda x: x[0])
			def getBestPairByCost():
				# コストをすべて計算
				costList=[]
				for job in jobs:
					for sol in sols:
						costList.append((sol.askCalcCost(job),sol,job))
				# 最小コストのものを選択
				return min(costList,key=lambda x: x[0])
			
			actAns=getBestPairByDeadline()
			if actAns==None:
				actAns=getBestPairByCost()
			print(actAns)
			job=actAns[2]
			# 計算できないジョブの可能性を調べる
			
			if job.getFailedCont()>10:
				with self.log as log:
					log.appendln(f"{job} is bad job")
				# failedJobs.append(job)
			else:
				with self.log as log:
					log.appendln(f"start calc with {actAns}")
				# 問題がなければ最後にジョブを投げる
				actAns[1].calc(job)
			
			# if job in jobFailedCont:
				# jobFailedCont[job]+=1
				# with logger as log:
					# log.appendln(f"{job}'s cont is {jobFailedCont[job]}")
			# else:
				# jobFailedCont[job]=0
			
			# if jobFailedCont[job]>1:

class StatusFiler:
	def __init__(self,filename):
		self.filename=filename
	def get(self):
		try:
			with open(self.filename,mode="r",encoding="utf-8") as f:
				return json.load(f)
		except FileNotFoundError:
			return None
			
	def set(self,x):
		with open(self.filename,mode="w",encoding="utf-8") as f:
			json.dump(x,f,ensure_ascii=False,indent=2)

def main():
	
	Logger.paramikoLogSetting()
	
	ui=InterruptUserInterface()
	
	jobManager=JobManager()

	# 計算に参加するPC(ホスト)を登録します
	hosts={
		"itok13":HostManager(
			username="itok13",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok13"
		),
		"itok6":HostManager(
			username="itok6",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok6"
		),
		"itok5":HostManager(
			username="itok5",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok5"
		),
		"itok22":HostManager(
			username="itok22",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok22"
		),
		"itok20":HostManager(
			username="itok20",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok20"
		),
		"itok23":HostManager(
			username="itok23",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok23"
		),
		"itok23_ubuntu":HostManager(
			username="itok23",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok23",
			port=50022
		),
		"itok24":HostManager(
			username="itok24",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok24"
		),
		"itok27":HostManager(
			username="itok27",
			password="XXXX",
			hostname="192.168.XX.XX",
			logname="itok27"
		),
	}

	# それぞれのホスト上でどのソルバーを実行するかを設定します
	solverManager=SolverManager((
		SolverViaSSH(
			cmd="python run.py omp",
			host=hosts["itok5"],
			logname="itok5",
			costs={"fdtd":1.0},
			costMult=4.0
		),
		SolverViaSSH(
			cmd="python run.py acc",
			host=hosts["itok6"],
			logname="itok6",
			costs={"fdtd":1.0},
			costMult=1.0
		),
		SolverViaSSH(
			cmd="python run.py acc",
			host=hosts["itok13"],
			logname="itok13",
			costs={"fdtd":1.0},
			costMult=1.2
		),
		SolverViaSSH(
			cmd="python run.py omp",
			host=hosts["itok23_ubuntu"],
			logname="itok23",
			costs={"fdtd":1.0},
			costMult=1.2
		),
		# SolverViaSSH(
		# 	cmd="python run.py omp",
		# 	host=hosts["itok24"],
		# 	logname="itok24",
		# 	costs={"fdtd":1.0},
		# 	costMult=1.0
		# ),
		SolverViaSSH(
			cmd="python run.py omp",
			host=hosts["itok27"],
			logname="itok27",
			costs={"fdtd":1.0},
			costMult=6.0
		),
		
	))
	filer=StatusFiler("0rm_status.json")
	filedData=filer.get()
	if filedData!=None:
		solverManager.setStatus(filedData["solverManager"])
	def saver():
		filer.set({
			"solverManager":solverManager.getStatus(),
		})
	#time.sleep(1800)
	# try:
	isQuitFlag=False
	jobFailedCont=dict()
	# failedJobs=[]
	logger=Logger("main")
	matchingEngine=MatchingEngine(jobManager,solverManager)
	while True:
		if isQuitFlag:
			if solverManager.isAllSolversDoneJob():
				print("すべての終了を確認しました")
				break
		else:
			
			matchingEngine.check()
		solverManager.check()
		
		# ユーザからのコマンドを受け付けます
		uiCmd=ui.get()
		if uiCmd=="quit":
			print("終了フラグを立てます")
			isQuitFlag=True
		elif uiCmd=="quitnow":
			print("CtrlCによって終了します")
			solverManager.stopSolvers()
			isQuitFlag=True
		elif uiCmd=="save":
			saver()
		time.sleep(0.5)
		print(".",end="",flush=True)
		#saver()
	print("終了します")
	

if "__main__"==__name__:
	try:
		main()
	except KeyboardInterrupt:
		print("KeyboardInterruptによって終了します")
