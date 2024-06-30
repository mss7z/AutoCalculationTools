app=cf.GetApplication()

-- 外部コマンドを用いて指定秒数待ちます
-- このためこの関数はwindowsでしか動作しません
function sleep(t)
    os.execute(string.format("sleep %d",t))
end

-- レンズを削除します
function delLens()
    -- Deleted geometry component: cuboid "PLAlens"
    Union1_1 = project.Geometry["Union1"]
    Union1 = Union1_1.Children["Union1"]
    PLAlens = Union1.Children["PLAlens"]
    PLAlens:Delete()
end

-- 引数で与えられた名前で保存します
function saveWithDir(name)
    os.execute(string.format("mkdir %s",name))
    app:SaveAs(string.format("%s/%s",name,name))
end

-- FarFieldの名前を変更します
function renFarFieldLavel(name)
    -- Modified solution entity: hello
    StandardConfiguration1 = project.SolutionConfigurations["StandardConfiguration1"]
    FarField1 = StandardConfiguration1.FarFields["FarFieldBase"]
    properties = FarField1:GetProperties()
    properties.Label = name
    FarField1:SetProperties(properties)
end

-- autoBaseを読み込んで引数で与えられたパラメータを変更しモデルを作成します
function generator(tickness,portLineLength,wireRadius,prefix)
    project=app:OpenFile("./autoBase.cfx")
    
    name=string.format("auto_%s_t%04.1fmm_l%04.2fmm_r%04.2fmm",prefix,tickness,portLineLength,wireRadius)
    print(name)
    
    --レンズ周りの設定
    PLAticknessVar=project.Variables["PLAtickness"]
    if tickness==0.0 then
        delLens()
    else
        PLAticknessVar.Expression=string.format("%f",tickness)
    end
    
    project.Variables["PortLineLength"].Expression=string.format("%f",portLineLength)
    
    --project.Variables["WireRadius"].Expression=string.format("%f",wireRadius)
    
    -- Updating mesh parameters
    MeshSettings = project.Mesher.Settings
    properties = MeshSettings:GetProperties()
    properties.WireRadius = string.format("%f",wireRadius)
    MeshSettings:SetProperties(properties)
    
    --FarFieldの名前つけ
    renFarFieldLavel(string.format("ff_t%05.0fum_l%05.0fum_r%05.0fum",tickness*1000,portLineLength*1000,wireRadius*1000))
    
    -- Mesh the model
    project.Mesher:Mesh()
    saveWithDir(name)
end

-- 多重ループを用いてパラメータを作成しgeneratorを呼び出します
function paramGenerator(name)
    ticknessInterval=0.1
    ticknessFrom=0
    ticknessTo=30.0

    for i=ticknessFrom/ticknessInterval,ticknessTo/ticknessInterval do
        tickness=i*ticknessInterval
        
        generator(tickness,1.27/2,0.1,name)
        --単位はum
        --for portLineLength=250,1200,250 do
            --generator(tickness,portLineLength/1000,0.1)
            --sleep(30)
            --for wireRadius=1,80,10 do
            --    generator(tickness,portLineLength/1000,wireRadius/1000)
            --    sleep(30)
            --end
        --end
        -- RunFEKO
        --project.Launcher:RunFEKO()
        
    end
end



-- 以下で解法にかかわる設定を行っています
-- 最初のみ詳細に解説します

-- 解法FDTDで、メッシュ細かさはStandardで設定します

-- ベースとなるautoBase.cfxを開きます
project=app:OpenFile("./autoBase.cfx")

-- Solution settings modified
-- 解法の設定を行います
SolverSettings_1 = project.SolutionSettings.SolverSettings
properties = SolverSettings_1:GetProperties()
properties.MLFMMACASettings.ModelSolutionSolveType = cf.Enums.ModelSolutionSolveTypeEnum.MLFMM
properties.FDTDSettings.FDTDEnabled = true
SolverSettings_1:SetProperties(properties)

-- Updating mesh parameters
-- メッシュの細かさを設定します
MeshSettings = project.Mesher.Settings
properties = MeshSettings:GetProperties()
properties.MeshSizeOption = cf.Enums.MeshSizeOptionEnum.Standard
MeshSettings:SetProperties(properties)

-- ワイヤー太さの設定を行います
-- FDTDとMLFMMで設定を変更する必要があるためです
-- FDTDではIntrinsicWireRadiusEnabled = trueとします
VoxelSettings_1 = project.Mesher.VoxelSettings
properties = VoxelSettings_1:GetProperties()
properties.IntrinsicWireRadiusEnabled = true
VoxelSettings_1:SetProperties(properties)

-- ベースとなるautoBase.cfxを上書きします
app:Save()

-- paramGeneratorでモデルを作成します
paramGenerator("FDTD_Standard")




-- 解法FDTDで、メッシュ細かさはCoarseで設定します

project=app:OpenFile("./autoBase.cfx")

-- Solution settings modified
SolverSettings_1 = project.SolutionSettings.SolverSettings
properties = SolverSettings_1:GetProperties()
properties.MLFMMACASettings.ModelSolutionSolveType = cf.Enums.ModelSolutionSolveTypeEnum.MLFMM
properties.FDTDSettings.FDTDEnabled = true
SolverSettings_1:SetProperties(properties)

-- Updating mesh parameters
MeshSettings = project.Mesher.Settings
properties = MeshSettings:GetProperties()
properties.MeshSizeOption = cf.Enums.MeshSizeOptionEnum.Coarse
MeshSettings:SetProperties(properties)

VoxelSettings_1 = project.Mesher.VoxelSettings
properties = VoxelSettings_1:GetProperties()
properties.IntrinsicWireRadiusEnabled = true
VoxelSettings_1:SetProperties(properties)

app:Save()

paramGenerator("FDTD_Coarse")



-- 解法MLFMMで、メッシュ細かさはStandardで設定します

project=app:OpenFile("./autoBase.cfx")

-- Solution settings modified
SolverSettings_1 = project.SolutionSettings.SolverSettings
properties = SolverSettings_1:GetProperties()
properties.MLFMMACASettings.ModelSolutionSolveType = cf.Enums.ModelSolutionSolveTypeEnum.MLFMM
properties.FDTDSettings.FDTDEnabled = false
SolverSettings_1:SetProperties(properties)

-- Updating mesh parameters
MeshSettings = project.Mesher.Settings
properties = MeshSettings:GetProperties()
properties.MeshSizeOption = cf.Enums.MeshSizeOptionEnum.Standard
MeshSettings:SetProperties(properties)

VoxelSettings_1 = project.Mesher.VoxelSettings
properties = VoxelSettings_1:GetProperties()
properties.IntrinsicWireRadiusEnabled = false
VoxelSettings_1:SetProperties(properties)

app:Save()

paramGenerator("MLFMM_Standard")



-- 解法MLFMMで、メッシュ細かさはCoarseで設定します

project=app:OpenFile("./autoBase.cfx")

-- Solution settings modified
SolverSettings_1 = project.SolutionSettings.SolverSettings
properties = SolverSettings_1:GetProperties()
properties.MLFMMACASettings.ModelSolutionSolveType = cf.Enums.ModelSolutionSolveTypeEnum.MLFMM
properties.FDTDSettings.FDTDEnabled = false
SolverSettings_1:SetProperties(properties)

-- Updating mesh parameters
MeshSettings = project.Mesher.Settings
properties = MeshSettings:GetProperties()
properties.MeshSizeOption = cf.Enums.MeshSizeOptionEnum.Coarse
MeshSettings:SetProperties(properties)

VoxelSettings_1 = project.Mesher.VoxelSettings
properties = VoxelSettings_1:GetProperties()
properties.IntrinsicWireRadiusEnabled = false
VoxelSettings_1:SetProperties(properties)

app:Save()

paramGenerator("MLFMM_Coarse")
