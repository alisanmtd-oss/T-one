const api = window.tone;
const capabilities = [
  {id:'store-agent',kind:'agent',category:'店铺运营',name:'店铺运营 Agent',status:'已包含',description:'商品、订单、库存、履约和日常经营任务。'},
  {id:'content-agent',kind:'agent',category:'内容商品',name:'内容创作 Agent',status:'已包含',description:'商品文案、图片、短视频脚本和本地化。'},
  {id:'ads-agent',kind:'agent',category:'增长营销',name:'广告诊断 Agent',status:'已包含',description:'读取数据、解释原因并生成待确认方案，不自动花费。'},
  {id:'research-agent',kind:'agent',category:'市场研究',name:'市场研究 Agent',status:'已包含',description:'竞品、趋势、国家与渠道研究。'},
  {id:'shein-skill',kind:'skill',category:'平台运营',name:'SHEIN 运营 Skill',status:'已包含',description:'公开规则、商品准备和卖家工作流。'},
  {id:'shopee-skill',kind:'skill',category:'平台运营',name:'Shopee 运营 Skill',status:'已包含',description:'公开规则、商品与活动准备流程。'},
  {id:'listing-skill',kind:'skill',category:'内容商品',name:'商品上架 Skill',status:'已包含',description:'字段检查、标题关键词和批量表格准备。'},
  {id:'feedback-skill',kind:'skill',category:'质量售后',name:'反馈质量 Skill',status:'已包含',description:'归纳评价、退货与缺陷，形成改进任务。'},
  {id:'generic-mcp',kind:'mcp',category:'工具连接',name:'通用 HTTP MCP',status:'需配置',description:'登记自己的 MCP URL 和凭据；保存不代表已连接。'},
  {id:'filesystem-mcp',kind:'mcp',category:'本地文件',name:'文件系统 MCP',status:'需安装',description:'按项目目录授权文件访问，未安装时不会冒充可用。'},
  {id:'codex-cli',kind:'cli',category:'AI 工具',name:'Codex CLI',status:'需检测',description:'登记命令后检测本机路径，再按项目配置。'},
  {id:'gemini-cli',kind:'cli',category:'AI 工具',name:'Gemini CLI',status:'需检测',description:'登记命令后检测本机路径，再按项目配置。'},
  {id:'workbuddy-cli',kind:'cli',category:'AI 工具',name:'WorkBuddy / CodeBuddy CLI',status:'需检测',description:'仅在提供真实 CLI 命令时登记和检测。'}
];
let state={projects:[],connections:[]}, currentProjectId='', currentTaskId='', currentView='home', currentKind='agent';
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

function toast(text){const node=$('toast');node.textContent=text;node.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.hidden=true,2800)}
function activeProject(){return state.projects.find(item=>item.id===currentProjectId)}
function activeTask(){return activeProject()?.tasks?.find(item=>item.id===currentTaskId)}
function countTasks(){return state.projects.reduce((sum,item)=>sum+(item.tasks?.length||0),0)}
function connectionStatus(item){if(item.status==='detected')return '已检测';if(item.status==='not_detected')return '未检测到';if(item.status==='mcp_reachable')return '本次测试已连通';if(item.status==='mcp_failed')return '连通失败';return '已保存，未连接'}

function renderTree(){
  $('projectCount').textContent=`${state.projects.length} 个项目`;
  $('projectTree').innerHTML=state.projects.length?state.projects.map(project=>`<div class="project-node"><button class="project-row" data-project="${esc(project.id)}"><span>${esc(project.name)}</span><small>${project.tasks?.length||0}</small></button>${(project.tasks||[]).map(task=>`<button class="task-row ${task.id===currentTaskId?'active':''}" data-project="${esc(project.id)}" data-task="${esc(task.id)}">${esc(task.name)}</button>`).join('')}</div>`).join(''):'<div class="empty">还没有项目</div>';
  document.querySelectorAll('[data-task]').forEach(button=>button.onclick=()=>openTask(button.dataset.project,button.dataset.task));
  document.querySelectorAll('.project-row').forEach(button=>button.onclick=()=>{currentProjectId=button.dataset.project;$('taskDialog').showModal()});
}

function renderHome(){
  $('stats').innerHTML=[['项目',state.projects.length],['任务',countTasks()],['已登记连接',state.connections.length],['已检测 CLI',state.connections.filter(item=>item.status==='detected').length]].map(([label,value])=>`<div class="stat"><b>${value}</b><small>${label}</small></div>`).join('');
  const tasks=state.projects.flatMap(project=>(project.tasks||[]).map(task=>({...task,projectId:project.id,projectName:project.name}))).sort((a,b)=>String(b.updatedAt||b.createdAt).localeCompare(String(a.updatedAt||a.createdAt))).slice(0,6);
  $('recentTasks').innerHTML=tasks.length?tasks.map(task=>`<button class="card" data-recent-project="${esc(task.projectId)}" data-recent-task="${esc(task.id)}"><b>${esc(task.name)}</b><small>${esc(task.projectName)} · ${task.messages?.length||0} 条对话 · ${task.files?.length||0} 个文件</small></button>`).join(''):'<div class="empty">先新建项目，再建立一个具体任务。任务的历史和文件会保存在独立目录。</div>';
  document.querySelectorAll('[data-recent-task]').forEach(button=>button.onclick=()=>openTask(button.dataset.recentProject,button.dataset.recentTask));
}

function renderTask(){
  const project=activeProject(),task=activeTask();if(!project||!task)return showView('home');
  $('taskName').textContent=task.name;$('taskPath').textContent=`${project.name} / tasks / ${task.id}`;
  const assigned=capabilities.filter(item=>(task.capabilities||[]).includes(item.id));
  $('capabilitySummary').textContent=assigned.length?assigned.map(item=>item.name).join(' · '):'未选择能力';
  $('messages').innerHTML=(task.messages||[]).length?(task.messages||[]).map(item=>`<div class="message ${item.role==='user'?'user':''}">${esc(item.text)}<small>${new Date(item.at).toLocaleString('zh-CN')}</small></div>`).join(''):'<div class="empty">这个任务还没有对话。说清目标后，记录会保存在当前任务，而不是混进其他项目。</div>';
  $('fileSummary').textContent=task.files?.length?`${task.files.length} 个附件`:'暂无附件';
  $('taskDetails').innerHTML=`<div class="detail"><b>项目</b><span>${esc(project.name)}</span></div><div class="detail"><b>状态</b><span>${esc(task.status)}</span></div><div class="detail"><b>Agent / Skill</b><span>${assigned.length} 项</span></div><div class="detail"><b>附件</b><span>${task.files?.length||0} 个</span></div><div class="detail"><b>任务目录</b><span>${esc(task.folder||'')}</span></div>`;
  const executors=state.connections.filter(item=>item.type==='cli'&&item.status==='detected');
  $('taskExecutor').innerHTML='<option value="">不调用 CLI</option>'+executors.map(item=>`<option value="${esc(item.id)}">${esc(item.name)}</option>`).join('');
  $('taskExecutor').value=executors.some(item=>item.id===task.executorId)?task.executorId:'';
  $('runCli').disabled=!$('taskExecutor').value;
}

function renderMarket(){
  const task=activeTask();$('marketTask').textContent=task?`加入当前任务：${task.name}`:'请先选择任务';
  const query=$('marketSearch').value.trim().toLowerCase(),category=$('marketCategory').value;
  const rows=capabilities.filter(item=>item.kind===currentKind&&(category==='all'||item.category===category)&&(!query||`${item.name} ${item.description} ${item.category}`.toLowerCase().includes(query)));
  $('marketGrid').innerHTML=rows.map(item=>{const selected=task?.capabilities?.includes(item.id);return `<article class="capability"><header><b>${esc(item.name)}</b><span class="pill">${esc(item.status)}</span></header><p>${esc(item.description)}</p><small>${esc(item.category)}</small><button class="secondary" data-capability="${esc(item.id)}" ${task?'':'disabled'}>${selected?'已加入当前任务':'加入当前任务'}</button></article>`}).join('')||'<div class="empty">当前分类没有匹配项</div>';
  document.querySelectorAll('[data-capability]').forEach(button=>button.onclick=async()=>{try{state=await api.assignCapability({projectId:currentProjectId,taskId:currentTaskId,capabilityId:button.dataset.capability});renderAll()}catch(error){toast(error.message)}});
}

function selectKind(kind){currentKind=kind;document.querySelectorAll('#marketTabs button').forEach(button=>button.classList.toggle('active',button.dataset.kind===kind));const categories=[...new Set(capabilities.filter(item=>item.kind===kind).map(item=>item.category))];$('marketCategory').innerHTML='<option value="all">全部分类</option>'+categories.map(item=>`<option>${esc(item)}</option>`).join('');renderMarket()}

function renderConnections(){
  for(const type of ['mcp','cli']){const node=$(type+'Connections'),items=state.connections.filter(item=>item.type===type);node.innerHTML=items.length?items.map(item=>`<article class="card connection-card"><b>${esc(item.name)}</b><small>${esc(item.target)}</small><span class="pill">${connectionStatus(item)}</span><div class="connection-actions">${type==='cli'?`<button class="secondary" data-detect="${esc(item.id)}">检测路径</button>`:`<button class="secondary" data-test-mcp="${esc(item.id)}">测试连通</button>`}<button class="danger" data-remove="${esc(item.id)}">删除</button></div></article>`).join(''):`<div class="empty">还没有登记 ${type.toUpperCase()}</div>`}
  document.querySelectorAll('[data-detect]').forEach(button=>button.onclick=async()=>{try{state=await api.detectCli({connectionId:button.dataset.detect});renderAll();toast('检测完成，状态已更新')}catch(error){toast(error.message)}});
  document.querySelectorAll('[data-test-mcp]').forEach(button=>button.onclick=async()=>{try{state=await api.testMcp({connectionId:button.dataset.testMcp});renderAll();toast('MCP 本次连通测试通过')}catch(error){state=await api.loadWorkspace();renderAll();toast(error.message)}});
  document.querySelectorAll('[data-remove]').forEach(button=>button.onclick=async()=>{try{state=await api.removeConnection({connectionId:button.dataset.remove});renderAll()}catch(error){toast(error.message)}});
}

function renderAll(){renderTree();renderHome();renderTask();renderMarket();renderConnections();$('workspacePath').textContent=state.workspacePath||''}
function showView(view){currentView=view;for(const id of ['home','task','market','connections','settings'])$(id+'View').hidden=id!==view;const titles={home:['工作台','每个项目一个文件夹，任务和资料不会混在一起'],task:[activeTask()?.name||'任务',activeProject()?.name||''],market:['能力市场','Agent、Skill、MCP、CLI 按用途分类'],connections:['MCP 与 CLI','登记、检测和项目配置分开管理'],settings:['设置','本地工作区与安全边界']};[$('pageTitle').textContent,$('pageSubtitle').textContent]=titles[view];document.querySelectorAll('[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===view));if(view==='market')renderMarket()}
function openTask(projectId,taskId){currentProjectId=projectId;currentTaskId=taskId;renderAll();showView('task')}

document.querySelectorAll('[data-view]').forEach(button=>button.onclick=()=>showView(button.dataset.view));
for(const id of ['newProject','heroNewProject'])$(id).onclick=()=>$('projectDialog').showModal();
$('newTask').onclick=()=>$('taskDialog').showModal();
$('openFolder').onclick=async()=>{try{const result=await api.openProjectFolder({projectId:currentProjectId});if(!result.ok)toast(result.error)}catch(error){toast(error.message)}};
$('attach').onclick=async()=>{try{state=await api.chooseFiles({projectId:currentProjectId,taskId:currentTaskId});renderAll()}catch(error){toast(error.message)}};
$('taskExecutor').onchange=async event=>{try{state=await api.setTaskExecutor({projectId:currentProjectId,taskId:currentTaskId,connectionId:event.target.value});renderAll()}catch(error){toast(error.message)}};
$('addConnection').onclick=()=>$('connectionDialog').showModal();
$('marketTabs').querySelectorAll('button').forEach(button=>button.onclick=()=>selectKind(button.dataset.kind));
$('marketSearch').oninput=renderMarket;$('marketCategory').onchange=renderMarket;

$('projectForm').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,data=new FormData(form);try{state=await api.createProject({name:data.get('name'),description:data.get('description')});form.reset();$('projectDialog').close();currentProjectId=state.projects[0].id;$('taskDialog').showModal();renderAll()}catch(error){toast(error.message)}};
$('taskForm').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,data=new FormData(form);try{state=await api.createTask({projectId:currentProjectId,name:data.get('name')});form.reset();$('taskDialog').close();const project=state.projects.find(item=>item.id===currentProjectId);openTask(currentProjectId,project.tasks[0].id)}catch(error){toast(error.message)}};
$('connectionForm').onsubmit=async event=>{event.preventDefault();const form=event.currentTarget,data=new FormData(form);try{state=await api.saveConnection(Object.fromEntries(data));form.reset();$('connectionDialog').close();renderAll();showView('connections')}catch(error){toast(error.message)}};
async function submitPrompt(runCli){const text=$('prompt').value.trim(),task=activeTask();if(!text||!task)return;const selected=capabilities.filter(item=>(task.capabilities||[]).includes(item.id)).filter(item=>item.kind==='agent'||item.kind==='skill').slice(0,5);task.messages=task.messages||[];task.messages.push({role:'user',text,at:new Date().toISOString()});$('prompt').value='';renderTask();if(runCli){const connectionId=task.executorId;if(!connectionId){toast('请先选择已检测的 CLI');return}const button=$('runCli');button.disabled=true;button.textContent='正在真实执行…';try{const result=await api.runCli({projectId:currentProjectId,taskId:currentTaskId,connectionId,prompt:text,capabilityNames:selected.map(item=>item.name)});if(!result.output)throw new Error('没有真实输出');task.messages.push({role:'assistant',text:result.output,at:new Date().toISOString()});toast('CLI 真实结果已写回当前任务')}catch(error){task.messages.push({role:'assistant',text:`CLI 运行失败：${error.message}`,at:new Date().toISOString()});toast(error.message)}finally{button.textContent='用所选 CLI 真实执行';renderTask()}}else{task.messages.push({role:'assistant',text:selected.length?`已保存到当前任务，当前只加载 ${selected.length} 项相关能力：${selected.map(item=>item.name).join('、')}。这是一条本地记录，不是 AI 真实回传。`:'已保存到当前任务。这是一条本地记录，不是 AI 真实回传；请选择 Agent/Skill 或已检测的 CLI。',at:new Date().toISOString()});renderTask()}try{await api.saveMessages({projectId:currentProjectId,taskId:currentTaskId,messages:task.messages})}catch(error){toast(error.message)}}
$('composer').onsubmit=event=>{event.preventDefault();submitPrompt(false)};
$('runCli').onclick=()=>submitPrompt(true);

(async()=>{try{state=await api.loadWorkspace();renderAll();selectKind('agent');showView('home')}catch(error){toast(`工作区启动失败：${error.message}`)}})();
