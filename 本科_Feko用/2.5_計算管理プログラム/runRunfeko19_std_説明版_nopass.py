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

basePath=os.getcwd()


print("hello runRunfeko")

class Logger:
	"""ログファイルの生成を行うクラスです"""
	logDir=os.path.join(basePath,"runRunfekoLogs")
	def __init__(self,filename="nanashi"):
		if not os.path.isdir(self.logDir):
			os.makedirs(self.logDir)
		self.timeStr=datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
		self.filename=filename
	def append(self,s):
		"""ログファイルに追加します"""
		self.f.write(datetime.datetime.now().strftime("[%Y%m%d_%H%M%S] ")+s)
	def appendln(self,s):
		"""ログファイルに改行付きで追加します"""
		self.append(s+"\n")
	def open(self):
		"""ログファイルを開きます"""
		self.f=open(os.path.join(self.logDir,self.timeStr+self.filename+".txt"),"a")
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
		if not os.path.isdir(cls.logDir):
			os.makedirs(cls.logDir)
		timeStr=datetime.datetime.now().strftime("%Y%m%d_%H%M%S_")
		paramiko.util.log_to_file(os.path.join(cls.logDir,timeStr+"paramiko.txt"))

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
		if self.getRunningSolverNum()>=2:
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
			sol.stopJob()
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
	def __init__(self,username,password,hostname,logname,parallelRunningMax=1):
		self.logger=Logger(f"host_{logname}")
		self.username=username
		self.password=password
		self.hostname=hostname
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
			client.connect(hostname=self.hostname,username=self.username,password=self.password,timeout=100)
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

class SolverViaSSH:
	"""SSHを経由したソルバーの代理人です"""
	def __init__(self,cmd,host,logname,costs,costMult=1.0):
		self.cmd=cmd
		self.logname=logname
		self.isRunningMem=multiprocessing.Value("i",False)
		self.errorcodeContMem=multiprocessing.Value("i",0)
		self.isCtlcFlagMem=multiprocessing.Value("i",False)
		
		self.canCalcTime=0
		self.host=host
		self.costs={key:cost*costMult for key,cost in costs.items()}
		
		self.currentRunningName=""
	def askCanCalc(self):
		"""ソルバーが計算可能であるかどうかを返します"""
		if not self.host.askCanCalc():
			return False
		if self.canCalcTime<time.time():
			#計算できるとき
			self.canCalcTime=0
		else:
			return False
		if self.errorcodeContMem.value>2:
			self.errorcodeContMem.value=0
			#後に再び計算を試みる
			self.canCalcTime=time.time()+120
			return False
		return not bool(self.isRunningMem.value)
	def askCalcCost(self,name):
		"""計算コストがいくらになるかを見積もります"""
		for cost in self.costs:
			if cost in name:
				#print(f"{name}は{self.costs[cost]}で計算可能")
				return self.costs[cost]
		else:
			return math.inf
	def jobCore(self,name):
		"""multiprocessingで呼び出されるSSHとSFTPによる通信シーケンスのコアです"""
		print("call job core")
		actCmd=self.cmd.format(name)
		#actCmd=f"sleep 30 && echo {name}"
		print("actCmd:",actCmd)
		localCd=os.path.join(basePath,name)
		print("run dir:",localCd)
		os.chdir(localCd)
		
		stopwatch=Stopwatch()
		timeoutStopwatch=Stopwatch()
		logger=Logger(f"job_{self.logname}_{name}")
		isSuccessCalc=True
		try:
			#https://self-development.info/python%E3%81%A7paramiko%E3%81%AB%E3%82%88%E3%82%8B%E3%83%95%E3%82%A1%E3%82%A4%E3%83%AB%E8%BB%A2%E9%80%81%E3%80%90no%EF%BC%81scp%E3%80%91/
			
			# 接続を開始します
			sshConnection=self.host.getSSHconnection()
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
			
			
			while True:
				# 標準出力のキューにデータがあればloggerで保存します
				if not stdoutQueue.empty():
					with logger as log:
						#log.append(f"returncode:{process.returncode}")
						log.append(stdoutQueue.get())
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
				if self.isCtlcFlagMem.value:
					#https://progrunner.hatenablog.jp/entry/2020/12/18/124259
					print("\x03", file=stdin, end="")
					self.isCtlcFlagMem.value=False
					print(f"{self.host}にCtrl-Cを送出しました")
					isSuccessCalc=False
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
			if not f"{name}.out" in [x.filename for x in remoteToLocalList]:
				print(f"{name}.outがないため失敗と推測")
				isSuccessCalc=False
			
			# リモート一時ディレクトリからダウンロードします
			# 計算に失敗していると判断できる際にはそこでリモート上のファイルを削除して完了します
			print(remoteToLocalList)
			for file in remoteToLocalList:
				fname=file.filename
				if stat.S_ISREG(file.st_mode):
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
			
		print("end cmd")
		# 計算が成功したかどうかのカウントをインクリメントまたはデクリメントします
		if isSuccessCalc:
			if self.errorcodeContMem.value>0:
				self.errorcodeContMem.value-=1
		else:
			self.errorcodeContMem.value+=1
			
		with logger as log:
			log.appendln(f"@:errorCont:{self.errorcodeContMem.value}")
			log.appendln("@:logVer:11")
			log.appendln("@:logEnd:")
		
		# 計算中であることを示すフラグを折ります
		self.isRunningMem.value=False
	
	def calc(self,name):
		"""メインプロセスのメインスレッド上で計算の命令を受け付けます"""
		print("call calc ")
		if not self.askCanCalc():
			print("internal error! askCanCalc()==False で calc() がコールされた")
			return
		#self.job=threading.Thread(target=jobCore)
		self.currentRunningName=name
		self.isRunningMem.value=True
		self.job=multiprocessing.Process(target=self.jobCore,args=(name,))
		self.job.start()
		print("end calc ")
	def waitJob(self):
		"""計算が完了するのを待ちます"""
		self.job.join()
	def stopJob(self):
		"""計算を終了します"""
		self.isCtlcFlagMem.value=True
		print("@SolverViaSSH stopJob フラグが立ちました")
	def isRunning(self):
		"""計算が実行しているかどうかを返しまします"""
		return self.isRunningMem.value
	def getRunningName(self):
		"""現在実行中または前回実行したモデル名を取得します"""
		return self.currentRunningName

class JobManager:
	"""ローカルのディレクトリからジョブ（モデル）の一覧を取得して管理します"""
	def __init__(self):
		self.nameList=[]
		self.reloadDir()
	@staticmethod
	def isDoneJobFromFile(name):
		"""ローカルのディレクトリ内に.outファイルがあるかどうかで計算が完了しているかどうかを判定します"""
		return os.path.isfile(os.path.join(name,name+".out"))
	def reloadDir(self,diff=[]):
		"""ローカルのディレクトリを再読み込みします"""
		def getCalcTarget():
			retTargets=[]
			targets=glob.glob("*/*.cfs")
			for target in targets:
				name=os.path.dirname(target)
				#print(name,end="...")
				if self.isDoneJobFromFile(name):
					#print("end")
					#retTargets.append(name)
					pass
				else:
					#print("MADA!")
					retTargets.append(name)
			return retTargets
		#self.nameList=getCalcTarget()
		self.nameList=[name for name in getCalcTarget() if not name in diff]
		#print(f"self.nameList {self.nameList}")
		return len(self.nameList)
	def next(self):
		"""次のジョブを取得します"""
		while True:
			if len(self.nameList)==0:
				return None
			ret=self.nameList.pop()
			if not self.isDoneJobFromFile(ret):
				break
		return ret
	def getJobs(self):
		"""まだ計算が完了していないすべてのジョブの名前を取得します"""
		return self.nameList
	def getJobCont(self):
		"""まだ計算が完了していないすべてのジョブの数を取得します"""
		return len(self.nameList)


def main():
	
	Logger.paramikoLogSetting()
	
	ui=InterruptUserInterface()

	jobManager=JobManager()

	# 計算に参加するPC(ホスト)を登録します
	hosts={
		"itok13":HostManager(
			username="itok13",
			password="xxxxxx",
			hostname="xxx.xxx.xxx.xxx",
			logname="itok13"
		),
		"itok6":HostManager(
			username="itok6",
			password="xxxxxx",
			hostname="xxx.xxx.xxx.xxx",
			logname="itok6"
		),
		"itok5":HostManager(
			username="itok5",
			password="xxxxxx",
			hostname="xxx.xxx.xxx.xxx",
			logname="itok5"
		),
		"itok22":HostManager(
			username="itok22",
			password="xxxxxx",
			hostname="xxx.xxx.xxx.xxx",
			logname="itok22"
		),
		"itok20":HostManager(
			username="itok20",
			password="xxxxxx",
			hostname="xxx.xxx.xxx.xxx",
			logname="itok20"
		),
		"itok23":HostManager(
			username="itok23",
			password="xxxxxx",
			hostname="xxx.xxx.xxx.xxx",
			logname="itok23"
		),
	}

	# それぞれのホスト上でどのソルバーを実行するかを設定します
	solverManager=SolverManager((
		SolverViaSSH(
			cmd="runfeko {} -np 4 --priority 4 --parallel-authenticate localonly",
			host=hosts["itok23"],
			logname="rrf2_itok23",
			costs={"MLFMM":1.0,"FDTD":2.0,},
			costMult=4.0
		),
		SolverViaSSH(
			cmd="runfeko {} -np 1 --priority 4 --parallel-authenticate localonly --use-gpu",
			host=hosts["itok13"],
			logname="rrf2_itok13_gpu1",
			costs={"FDTD":1.0,},
			costMult=5.0
		),
		SolverViaSSH(
			cmd="runfeko {} -np 4 --priority 4 --parallel-authenticate localonly",
			host=hosts["itok13"],
			logname="rrf2_itok13",
			costs={"MLFMM":1.0,},
			costMult=5.0
		),
		SolverViaSSH(
			cmd="runfeko {} -np 4 --priority 4 --parallel-authenticate localonly",
			host=hosts["itok6"],
			logname="rrf2_itok6",
			costs={"MLFMM":1.0,"FDTD":2.0,},
			costMult=10.0
		),
		SolverViaSSH(
			cmd="runfeko {} -np 4 --priority 4 --parallel-authenticate localonly",
			host=hosts["itok5"],
			logname="rrf2_itok5",
			costs={"MLFMM":1.0,"FDTD":2.0,},
			costMult=13.0
		),
        SolverViaSSH(
			cmd="runfeko {} -np 4 --priority 4 --parallel-authenticate localonly",
			host=hosts["itok22"],
			logname="rrf2_itok22",
			costs={"MLFMM":1.0,"FDTD":2.0,},
			costMult=15.0
		),
		SolverViaSSH(
			cmd="runfeko {} -np 1 --priority 4 --parallel-authenticate localonly --use-gpu",
			host=hosts["itok22"],
			logname="rrf2_itok22",
			costs={"FDTD":1.0,},
			costMult=13.0
		),
		SolverViaSSH(
			cmd="runfeko {} -np 1 --priority 4 --parallel-authenticate localonly --use-gpu",
			host=hosts["itok20"],
			logname="rrf2_itok20",
			costs={"FDTD":1.0,},
			costMult=7.0
		),
		
	))
	#time.sleep(1800)
	# try:
	isQuitFlag=False
	jobFailedCont=dict()
	failedJobs=[]
	logger=Logger("main")
	while True:
		if isQuitFlag:
			if solverManager.isAllSolversDoneJob():
				print("すべての終了を確認しました")
				break
		else:
			sols=solverManager.getSolvers()
			jobManager.reloadDir(solverManager.getRunningJobs()+failedJobs)
			
			if jobManager.getJobCont()==0:
				print("c",end="",flush=True)
			
			elif len(sols)!=0:
				# ソルバーに空きがあるとき
				# コストをすべて計算
				costList=[]
				for job in jobManager.getJobs():
					for sol in sols:
						costList.append((sol.askCalcCost(job),sol,job))
				# 最小コストのものを選択
				actAns=min(costList,key=lambda x: x[0])
				print(actAns)
				job=actAns[2]
				# 計算できないジョブの可能性を調べる
				if job in jobFailedCont:
					jobFailedCont[job]+=1
					with logger as log:
						log.appendln(f"{job}'s cont is {jobFailedCont[job]}")
				else:
					jobFailedCont[job]=0
				
				if jobFailedCont[job]>1:
					with logger as log:
						log.appendln(f"{job} is bad job")
					failedJobs.append(job)
				else:
					with logger as log:
						log.appendln(f"start calc with {actAns}")
					# 問題がなければ最後にジョブを投げる
					actAns[1].calc(job)
		
		# ユーザからのコマンドを受け付けます
		uiCmd=ui.get()
		if uiCmd=="quit":
			print("終了フラグを立てます")
			isQuitFlag=True
		elif uiCmd=="quitnow":
			print("CtrlCによって終了します")
			solverManager.stopSolvers()
			isQuitFlag=True
		time.sleep(0.5)
		print(".",end="",flush=True)
		
	print("終了します")

if "__main__"==__name__:
	try:
		main()
	except KeyboardInterrupt:
		print("KeyboardInterruptによって終了します")
