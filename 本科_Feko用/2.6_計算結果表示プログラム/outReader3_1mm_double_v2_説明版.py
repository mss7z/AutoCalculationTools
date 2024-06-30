import enum
from enum import auto
import glob
import parse
import os
import matplotlib.pyplot as plt
import re

#このプログラム上において
# FF = Far Field

@enum.unique
class OutReadState(enum.IntEnum):
	searchFF=auto()
	waitFirstLineOfFF=auto()
	readFF=auto()
	endOfRead=auto()

@enum.unique
class FFColumn(enum.IntEnum):
	THETA=0
	PHI=1
	ETHETA_magn=2
	ETHETA_phase=3
	EPHI_magn=4
	EPHI_phase=5
	dB_vert=6
	dB_horiz=7
	dB_total=8
	POLAR_axial_r=9
	POLAR_angle=10
	POLAR_direction=11
	FAR_FIELD_COLUMN_LEN=12

class OutReader:
	"""Fekoの出力ファイルをパースして読み取ります
	ステートマシン的な実装になっています"""
	def __init__(self,path):
		self.path=path
		#print(path)
		#input()
		self.readState=OutReadState.searchFF
		self.readContInState=0
		
	def nextState(self):
		"""ステートを次にすすめる"""
		self.readState+=1
		self.readContInState=0
		
	def procLine(self,line):
		"""ステートの状態にしたがって関数を呼び出します"""
		(eval(f"self.{OutReadState(self.readState).name}_proc"))(line)
	
	def searchFF_proc(self,line):
		"""farFieldを探しているステートです"""
		#if "VALUES OF THE SCATTERED ELECTRIC FIELD STRENGTH IN THE FAR FIELD in V" in line:
		if "Far field request with name: ff" in line:
			self.nextState()
			#print(f"{self.getName()}")
	def waitFirstLineOfFF_proc(self,line):
		"""farFieldの最初のラインを待っているステートです"""
		#print(f"{self.readContInState}:{line}")
		if self.readContInState>=11:
			self.nextState()
	def readFF_proc(self,line):
		"""farFieldを読み込むステートです"""
		if line=="":
			self.nextState()
			return
		column=line.split()
		#print(column)
		if len(column)!=FFColumn.FAR_FIELD_COLUMN_LEN:
			raise RuntimeError("column長が一致しない")
		#print(f"{column[FFColumn.THETA]}_{column[FFColumn.PHI]}")
		self.farField[f"{column[FFColumn.THETA]}_{column[FFColumn.PHI]}"]=column
		
	def read(self):
		"""ファイルを読み込み、self.farFieldに格納します"""
		self.farField=dict()
		with open(self.path,"r") as f:
			while True:
				line=f.readline()
				if line=="":
					break
				self.procLine(line.replace("\n",""))
				if self.readState==OutReadState.endOfRead:
					break
				self.readContInState+=1
	
	def getName(self):
		"""モデル名を取得します"""
		#pathからbasenameを取り出して拡張子を削除
		#https://note.nkmk.me/python-os-basename-dirname-split-splitext/
		return os.path.splitext(os.path.basename(self.path))[0]
	def getFF(self):
		"""パースされたfarField情報を読み取ります"""
		return self.farField

def plotScatter(x,y):
	"""2Dの散布図を描きます"""
	fig=plt.figure()
	ax=fig.add_subplot(111)
	ax.scatter(x,y,c="b")
	ax.plot(x,y,c="b")
	plt.show()

def convToGlob(origin):
	"""globでのワイルドカード表現に変換します"""
	ret=re.sub(r"(\{.:.\})",r"*",origin)
	print(ret)
	return ret

def pickUpXY(fname,keyInFile):
	"""XYの説明変数を正規表現で表現したfname,keyInFileをもとに取り出し、dict(dict( farFieldの横データ ))の構造にして返します"""
	outPathList=glob.glob("{0:}/{0:}.out".format(convToGlob(fname)))
	print(outPathList)
	
	retDict={}
	
	for outPath in outPathList:
		try:
			reader=OutReader(outPath)
			reader.read()
			
			for ffKey in reader.getFF():
				#print(ffKey)
				
				keyParsed=parse.parse(keyInFile,ffKey)
				if keyParsed==None:
					continue
				
				fnameParsed=parse.parse(fname,reader.getName())
				
				elementDict=fnameParsed.named
				elementDict.update(keyParsed.named)
				
				if elementDict["x"] not in retDict:
					retDict[elementDict["x"]]=dict()
				retDict[elementDict["x"]][elementDict["y"]]=reader.getFF()[ffKey]
				
				#retList.append(elementDict)
		except Exception as e:
			print(repr(e))
	
	return retDict
	
def pickUpX(fname,keyInFile):
	"""Xの説明変数を正規表現で表現したfname,keyInFileをもとに取り出し、dict( farFieldの横データ )の構造にして返します"""
	outPathList=glob.glob("{0:}/{0:}.out".format(convToGlob(fname)))
	print(outPathList)
	
	retDict={}
	
	for outPath in outPathList:
		try:
			reader=OutReader(outPath)
			reader.read()
			
			for ffKey in reader.getFF():
				#print(ffKey)
				
				keyParsed=parse.parse(keyInFile,ffKey)
				if keyParsed==None:
					continue
				
				fnameParsed=parse.parse(fname,reader.getName())
				
				elementDict=fnameParsed.named
				elementDict.update(keyParsed.named)
				
				#print(explanatoryVars)
				
				#elementDict["data"]=reader.getFF("ffKey")
				
				retDict[elementDict["x"]]=reader.getFF()[ffKey]
				
				#retList.append(elementDict)
		except Exception as e:
			print(repr(e))
	
	return retDict
	
def convToXYZ(dictDict,objectiveVar):
	"""三次元のヒートマップに入力できる形式に変換します
	dictDictはpickUpXYの返り値を用います"""
	#XYの範囲を調べる
	xSet=set()
	ySet=set()
	
	for dd in dictDict:
		xSet.add(dd)
		for d in dictDict[dd]:
			ySet.add(d)
	
	print("xSet",xSet)
	print("ySet",ySet)
	
	xList=sorted(list(xSet))
	yList=sorted(list(ySet))
	
	print("yList",yList)
	
	baseList=[]
	#2次元配列を作る
	for x in xList:
		baseList.append([0.0 if dictDict.get(x).get(y) is None else float(dictDict[x][y][objectiveVar]) for y in yList])
	
	#print(baseList)
	return xList,yList,baseList

def plotColor(x,y,z):
	"""ヒートマップを表示します"""
	plt.pcolor(x,y,z,cmap="viridis")
	
	pp=plt.colorbar (orientation="vertical") # カラーバーの表示 
	pp.set_label("Label", fontname="Arial", fontsize=24) #カラーバーのラベル
	
	plt.show()

def graphMaker(fname,keyInFile,objectiveVar):
	"""ファイル名やキーを正規表現されたものをもとに目的変数を選択してヒートマップにする糖衣的な高級な関数"""
	dictDict=pickUpXY(fname,keyInFile)
	print(dictDict)
	x,y,z=convToXYZ(dictDict,objectiveVar)
	plotColor(y,x,z)

def graphMaker2D(fname,keyInFile,objectiveVar):
	"""ファイル名やキーを正規表現されたものをもとに目的変数を選択して散布図にする糖衣的な高級な関数"""
	dic=pickUpX(fname,keyInFile)
	print(dic)
	
	x=[]
	y=[]
	for k,v in dic.items():
		x.append(k)
		y.append(float(v[objectiveVar]))
	plotScatter(x,y)

def graphData2D(fname,keyInFile,objectiveVar):
	"""グラフを作るのではなく、ファイル名やキーを正規表現されたものをもとに目的変数を選択して返す高級な関数"""
	dic=pickUpX(fname,keyInFile)
	print(dic)
	
	x=[]
	y=[]
	for k,v in dic.items():
		x.append(k)
		y.append(float(v[objectiveVar]))
	return x,y

def graphDataSaver2D(x,y,name):
	"""graphData2Dのデータを保存する"""
	with open(name,"w") as f:
		for xv,yv in zip(x,y):
			f.write(f"{xv},{yv}\n")
	return x,y

def graphDataLoader2D(name):
	"""graphData2Dのデータを読み込む"""
	x=[]
	y=[]
	with open(name,"r") as f:
		while True:
			line=f.readline()
			if line=="":
				break
			xv,yv=line.split(",")
			x.append(float(xv))
			y.append(float(yv))
	return x,y

def graphDataCache2D(getFunc,name):
	"""graphData2Dのデータをキャッシュする"""
	fname=name+".txt"
	if not os.path.isfile(fname):
		x,y=graphDataSaver2D(*getFunc(),fname)
	else:
		x,y=graphDataLoader2D(fname)
	return x,y

def thinningData1mmInterval(x,y):
	"""初期のバージョンにあった1mm間隔のグラフを再現する"""
	retx=[]
	rety=[]
	for xv,yv in zip(x,y):
		if xv.is_integer():
			retx.append(xv)
			rety.append(yv)
	return retx,rety
def graphDataCache2Dthinning(getFunc,name):
	"""初期のバージョンにあった1mm間隔のグラフを再現するthinningData1mmIntervalのデータをキャッシュする"""
	fname=name+".txt"
	if not os.path.isfile(fname):
		x,y=graphDataSaver2D(*getFunc(),fname)
	else:
		x,y=graphDataLoader2D(fname)
	x,y=thinningData1mmInterval(x,y)
	return x,y
		
	
def main():
	"""各値を設定して、グラフに表示する"""
	fig=plt.figure()
	plt.rcParams['font.family'] = 'Meiryo'
	plt.rcParams["font.size"] = 18
	plt.rcParams['xtick.direction'] = 'in'
	plt.rcParams['ytick.direction'] = 'in'
	fig.subplots_adjust(top=0.9)
	
	ax=fig.add_subplot(211)
	
	ax.set_xlabel("PLAレンズの厚さ[mm]",  weight = "light")
	ax.set_ylabel("ホーンアンテナ正面での利得[dBi]",  weight = "light")
	ax.grid()
	ax.set_xlim(0,31)
	ax.set_ylim(21,24.5)
	
	
	x,y=graphDataCache2D(lambda: graphData2D("auto_MLFMM_Coarse_t{x:f}mm_l0.64mm_r0.10mm","0.00_0.00",FFColumn.dB_total),"gd_MLFMM_Coarse_outReader3_1mm_double")
	ax.plot(x,y,"ob-",label="MLFMM_Coarse",markersize=2)
	ax.hlines(y[0],x[0],x[-1],linestyles="solid",colors="b")
	
	ax.legend()
	
	
	ax=fig.add_subplot(212)
	
	ax.set_xlabel("PLAレンズの厚さ[mm]",  weight = "light")
	ax.set_ylabel("ホーンアンテナ正面での利得[dBi]",  weight = "light")
	ax.grid()
	ax.set_xlim(0,31)
	ax.set_ylim(21,24.5)
	
	x,y=graphDataCache2Dthinning(lambda: graphData2D("auto_MLFMM_Coarse_t{x:f}mm_l0.64mm_r0.10mm","0.00_0.00",FFColumn.dB_total),"gd_MLFMM_Coarse_outReader3_1mm_double_interval")
	ax.plot(x,y,"ob-",label="MLFMM_Coarse",markersize=2)
	ax.hlines(y[0],x[0],x[-1],linestyles="solid",colors="b")
	
	# x,y=graphDataCache2Dthinning(lambda: graphData2D("auto_FDTD_Coarse_t{x:f}mm_l0.64mm_r0.10mm","0.00_0.00",FFColumn.dB_total),"gd_FDTD_Coarse")
	# ax.plot(x,y,"^r-",label="FDTD_Coarse")
	# ax.hlines(y[0],x[0],x[-1],linestyles="solid",colors="r")
	
	# x,y=graphDataCache2Dthinning(lambda: graphData2D("auto_MLFMM_Standard_t{x:f}mm_l0.64mm_r0.10mm","0.00_0.00",FFColumn.dB_total),"gd_MLFMM_Standard")
	# ax.plot(x,y,">c--",label="MLFMM_Standard")
	# ax.hlines(y[0],x[0],x[-1],linestyles="dashed",colors="c")
	
	# x,y=graphDataCache2Dthinning(lambda: graphData2D("auto_FDTD_Standard_t{x:f}mm_l0.64mm_r0.10mm","0.00_0.00",FFColumn.dB_total),"gd_FDTD_Standard")
	# ax.plot(x,y,"<g--",label="FDTD_Standard")
	# ax.hlines(y[0],x[0],x[-1],linestyles="dashed",colors="g")
	
	# x,y=graphData2D("auto_MLFMM_Coarse_t{x:f}mm_l0.64mm_r0.10mm","0.00_0.00",FFColumn.dB_total)
	# ax.scatter(x,y,c="b")
	# ax.plot(x,y,c="b")
	
	# x,y=graphData2D("auto_FDTD_Coarse_t{x:f}mm_l0.64mm_r0.10mm","0.00_0.00",FFColumn.dB_total)
	# ax.scatter(x,y,c="r")
	# ax.plot(x,y,c="r")
	
	ax.legend()
	
	
	plt.show()

		

	#plotScatter(atsusa,val)
if "__main__"==__name__:
	main()