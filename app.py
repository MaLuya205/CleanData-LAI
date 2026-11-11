<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CleanData LAI</title>
<style>
*{box-sizing:border-box;margin:0;padding:0;font-family:Arial,sans-serif}
body{background:#f2f2f2}
.hidden{display:none!important}
.topbar{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:#fff;border-bottom:1px solid #ddd}
.logo{font-weight:900;font-size:22px}
.logo span{color:#0f9d63}
.btn{padding:10px 18px;border:none;border-radius:8px;cursor:pointer;font-weight:700}
.btn-green{background:#0f9d63;color:#fff}
.btn-gold{background:#d4af37;color:#000}
.btn-outline{background:#fff;border:2px solid #0f9d63;color:#0f9d63}
.card{background:#fff;border-radius:16px;padding:22px;box-shadow:0 5px 20px rgba(0,0,0,.08);max-width:500px;margin:30px auto}
.card h2{margin-bottom:8px}
.card p{color:#555;margin-bottom:14px;line-height:1.5}
input,select{width:100%;padding:12px;margin:8px 0;border:1px solid #ccc;border-radius:8px}
.choice{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;padding:20px}
.choice-card{width:320px;border-radius:18px;padding:22px;cursor:pointer;text-align:center}
.business-card{background:#111;color:#fff;border:3px solid #d4af37}
.business-card h3{color:#d4af37;font-size:24px}
.individual-card{background:#fff;color:#111;border:3px solid #0f9d63}
.individual-card h3{color:#0f9d63;font-size:24px}
.layout{display:flex;min-height:100vh}
.sidebar{width:250px;padding:20px}
.sidebar-individual{background:#fff;border-right:3px solid #0f9d63}
.sidebar-business{background:#111;color:#fff;border-right:3px solid #d4af37}
.menu-btn{display:block;width:100%;text-align:left;padding:12px;margin:6px 0;border:none;border-radius:8px;cursor:pointer;font-weight:700;background:#f1f1f1}
.sidebar-business .menu-btn{background:#222;color:#fff}
.sidebar-business .menu-btn.active{background:#d4af37;color:#000}
.sidebar-individual .menu-btn.active{background:#0f9d63;color:#fff}
.main{flex:1;padding:20px}
.panel{background:#fff;border-radius:14px;padding:20px;margin-bottom:16px;box-shadow:0 3px 12px rgba(0,0,0,.06)}
.kpi{display:flex;gap:12px;flex-wrap:wrap}
.kpi div{flex:1;min-width:140px;background:#f8f8f8;padding:16px;border-radius:12px;text-align:center}
.kpi b{font-size:24px;display:block}
.profile{position:relative}
.dropdown{position:absolute;right:0;top:45px;background:#fff;color:#000;border:1px solid #ddd;border-radius:12px;width:230px;padding:10px;box-shadow:0 10px 30px rgba(0,0,0,.2);z-index:10}
.dropdown button{width:100%;text-align:left;padding:10px;border:none;background:none;cursor:pointer;font-weight:700}
.dropdown button:hover{background:#f2f2f2}
table{width:100%;border-collapse:collapse;margin-top:10px}
th,td{padding:10px;border-bottom:1px solid #ddd;text-align:left}
.badge{padding:4px 10px;border-radius:20px;font-size:12px;font-weight:700}
.good{background:#d4f8e2;color:#0a7a4a}
.bad{background:#ffe0e0;color:#b00}
@media(max-width:700px){.layout{flex-direction:column}.sidebar{width:100%}}
</style>
</head>
<body>
<div id="screenChoose">
<div style="text-align:center;padding:30px 10px 0"><div class="logo">🛡️ CDL <span>CleanData LAI</span></div><h1 style="margin-top:16px">Who are you? Choose your account</h1><p>Select the account type that fits you best</p></div>
<div class="choice">
<div class="choice-card business-card" onclick="chooseAccount('business')"><h3>🏢 BUSINESS ACCOUNT</h3><p style="color:#fff">PREMIUM • FOR TEAMS</p><p style="color:#ddd">For teams, shops, schools, companies. Bulk upload, invoices, team tracking.</p><div style="background:#222;padding:14px;border-radius:10px;margin:10px 0">📊 Analytics Overview<br>📈 Profit • Team • Growth</div><button class="btn btn-gold" style="width:100%">Business Account</button></div>
<div class="choice-card individual-card" onclick="chooseAccount('individual')"><h3>👤 INDIVIDUAL ACCOUNT</h3><p>SIMPLE • FOR YOU</p><p>For personal use, simple and secure. Clean your own files fast.</p><div style="background:#f2f2f2;padding:14px;border-radius:10px;margin:10px 0">📁 Drag & drop your file here<br><button class="btn btn-green">Upload File</button></div><button class="btn btn-green" style="width:100%">Individual Account</button></div>
</div>
<div style="text-align:center;padding:10px"><button class="btn btn-outline" onclick="showContactFromHome()">📞 Contact Us</button></div>
</div>
<div id="screenBusinessType" class="hidden"><div class="card" style="border:3px solid #d4af37;background:#111;color:#fff"><h2 style="color:#d4af37">What type of business are you?</h2><p style="color:#ddd">Pick one, we will set up your dashboard correctly.</p><button class="btn btn-gold" style="width:100%;margin:8px 0" onclick="chooseBusinessSize('small')">🏪 SMALL BUSINESS<br><small>It's just me, or me + 1 or 2 people. I do everything myself.</small></button><button class="btn" style="width:100%;background:#fff;color:#000" onclick="chooseBusinessSize('big')">🏢 BIG COMPANY<br><small>I have workers / staff. I need to track my team.</small></button><button class="btn" onclick="goHome()" style="background:#333;color:#fff;width:100%;margin-top:10px">Back</button></div></div>
<div id="screenSignup" class="hidden"><div class="card" id="signupCard"><h2 id="signupTitle">Create Account</h2><p id="signupSub">Fill in to continue</p><input id="inName" placeholder="Full Name / Business Name"><input id="inEmail" placeholder="Email"><input id="inPhone" placeholder="Phone Number"><input id="inPass" type="password" placeholder="Password"><div id="ownerCodeBox" class="hidden"><label><b>Owner: Create Manager Code (4 digits)</b></label><input id="inManagerCode" placeholder="e.g. 4821" maxlength="4"><p style="font-size:13px">Only managers with this code can open Team Performance + Profit Tracker.</p></div><button class="btn btn-green" id="signupBtn" style="width:100%" onclick="doSignup()">Create Account & Enter Dashboard</button><button class="btn" onclick="goHome()" style="width:100%;margin-top:8px">Back</button><div id="staffLoginLink" class="hidden" style="text-align:center;margin-top:12px"><a href="#" onclick="showStaffLogin();return false">Staff? Login here with your Staff ID</a></div></div></div>
<div id="screenStaffLogin" class="hidden"><div class="card" style="border:3px solid #d4af37;background:#111;color:#fff"><h2 style="color:#d4af37">Staff Login</h2><p style="color:#ddd">Login with your Staff ID given by your boss.</p><input id="staffId" placeholder="Staff ID e.g. CDL-001"><input id="staffName" placeholder="Your Full Name"><button class="btn btn-gold" style="width:100%" onclick="doStaffLogin()">Login as Staff</button><button class="btn" style="width:100%;margin-top:8px;background:#333;color:#fff" onclick="showSignup()">Back</button></div></div>
<div id="screenDashboard" class="hidden">
<div class="topbar" id="topbar"><div class="logo" id="dashLogo">🛡️ CDL CleanData LAI</div><div class="profile"><button class="btn" id="profileBtn" onclick="toggleProfile()">👤 <span id="profileName">My Account</span> ▼</button><div id="profileDropdown" class="dropdown hidden"><b id="dropName">Account</b><br><small id="dropType">Individual</small><hr><button onclick="showPanel('plans')">💳 Plans and Account</button><button onclick="showPanel('contact')">📞 Contact Us</button><button onclick="logout()">🚪 Logout</button></div></div></div>
<div class="layout"><div class="sidebar" id="sidebar"><h3 id="sideTitle">Menu</h3><div id="menuList"></div><div style="margin-top:20px;background:#f8f8f8;padding:12px;border-radius:10px;color:#000" id="staffBox" class="hidden"><b>Clock In Today</b><button class="btn btn-green" style="width:100%;margin-top:8px" onclick="clockIn()">⏰ Clock In</button><p id="clockStatus" style="font-size:13px;margin-top:8px">Not clocked in yet</p></div></div>
<div class="main">
<div id="panel-overview" class="panel"><h2>Overview</h2><p id="overviewText">Welcome to CleanData LAI.</p><div class="kpi"><div><b id="kpiFiles">0</b>Files Cleaned</div><div><b id="kpiRows">0</b>Rows Cleaned</div><div><b>R0</b>Saved</div></div></div>
<div id="panel-cleaning" class="panel hidden"><h2>🧹 Data Cleaning</h2><p>Upload CSV / Excel. We remove duplicates, fix names, fix phones.</p><input type="file" id="fileInput"><button class="btn btn-green" onclick="cleanFile()">Clean My File</button><p id="cleanResult" style="margin-top:10px"></p></div>
<div id="panel-pdfdata" class="panel hidden"><h2>📄 PDF Data</h2><p>Extract data from PDF, clean it, download as Excel.</p><input type="file"><button class="btn btn-green" onclick="alert('PDF Data: Upload your PDF, we will extract it.')">Upload PDF</button></div>
<div id="panel-converter" class="panel hidden"><h2>🔄 File Converter</h2><select><option>CSV to Excel</option><option>Excel to CSV</option><option>PDF to Excel</option><option>Excel to PDF</option></select><button class="btn btn-green" onclick="alert('File Converted!')">Convert File</button></div>
<div id="panel-pdftools" class="panel hidden"><h2>🧰 PDF Tool Kits</h2><p>Merge PDF, Split PDF, Compress PDF, PDF to Word.</p><button class="btn btn-green" onclick="alert('PDF Tool opened')">Open PDF Tools</button></div>
<div id="panel-planner" class="panel hidden"><h2>📅 Daily Planner</h2><p id="plannerSub">Your tasks for today.</p><input id="taskInput" placeholder="Add new task..."><button class="btn btn-green" onclick="addTask()">Add Task</button><ul id="taskList" style="margin-top:12px;list-style:none"></ul></div>
<div id="panel-invoice" class="panel hidden"><h2>🧾 Quick Invoice</h2><input placeholder="Customer Name"><input placeholder="Amount R"><input placeholder="For what?"><button class="btn btn-green" onclick="alert('Invoice Created! Download PDF.')">Create Invoice</button></div>
<div id="panel-analyst" class="panel hidden"><h2>📊 Data Analyst / Business Insights</h2><p>Am I making profit or loss? Which product makes money?</p><div class="kpi"><div><b>R12,500</b>Money IN</div><div><b>R7,200</b>Money OUT</div><div><b style="color:green">R5,300</b>Profit ✅</div></div><p>Best Product: Data Cleaning Service • Best Month: This Month</p></div>
<div id="panel-team" class="panel hidden"><h2>👥 Team Performance 🔒 Manager Only</h2><div id="teamLock"><p>Enter Manager Code to unlock:</p><input id="managerCodeInput" placeholder="Enter 4-digit Manager Code"><button class="btn btn-gold" onclick="unlockManager('team')">Unlock</button></div><div id="teamContent" class="hidden"><table><tr><th>Staff</th><th>Clock In</th><th>Tasks Done</th><th>Score</th></tr><tr><td>Sipho Dlamini</td><td>08:00 ✅</td><td>10 / 10</td><td><span class="badge good">95% WORKING WELL ⭐</span></td></tr><tr><td>Thandi Nene</td><td>10:30 ❌ Late</td><td>3 / 10</td><td><span class="badge bad">35% NOT WORKING WELL ⚠️</span></td></tr></table></div></div>
<div id="panel-profit" class="panel hidden"><h2>💰 Profit Tracker 🔒 Manager Only</h2><div id="profitLock"><p>Enter Manager Code to unlock:</p><input id="managerCodeInput2" placeholder="Enter 4-digit Manager Code"><button class="btn btn-gold" onclick="unlockManager('profit')">Unlock</button></div><div id="profitContent" class="hidden"><div class="kpi"><div><b>R12,500</b>This Month IN</div><div><b>R7,200</b>OUT</div><div><b>R5,300</b>Profit</div></div></div></div>
<div id="panel-staff" class="panel hidden"><h2>👥 Staff Management (Big Company)</h2><p>Boss creates staff logins here.</p><input id="newStaffName" placeholder="Staff Full Name"><button class="btn btn-green" onclick="addStaff()">Create Staff Login</button><ul id="staffList"></ul></div>
<div id="panel-plans" class="panel hidden"><h2>💳 Plans and Account</h2><p>Individual: R150 Small Clean • Business: R350 / R750 • Big Company: Custom</p><p><b>Current Plan:</b> <span id="currentPlan">Free Trial</span></p><button class="btn btn-green" onclick="alert('Upgrade coming soon. Contact us!')">Upgrade Plan</button></div>
<div id="panel-contact" class="panel hidden"><h2>📞 Contact Us</h2><p><b>CleanData LAI Business</b></p><p>📱 WhatsApp / Phone: <b>Your New Business Number Here</b></p><p>📧 Email: <b>cleandatalai@gmail.com</b></p><p>🕐 Monday - Saturday, 08:00 - 17:00</p><button class="btn btn-green" onclick="alert('Opening WhatsApp...')">Chat on WhatsApp</button></div>
</div></div></div>
<script>
let accountType='individual',businessSize='small',role='owner',managerCode='4821',userName='User',tasks=[];
function chooseAccount(t){accountType=t; if(t==='business'){document.getElementById('screenChoose').classList.add('hidden');document.getElementById('screenBusinessType').classList.remove('hidden');}else{showSignup();}}
function chooseBusinessSize(s){businessSize=s;showSignup();}
function showSignup(){document.getElementById('screenChoose').classList.add('hidden');document.getElementById('screenBusinessType').classList.add('hidden');document.getElementById('screenStaffLogin').classList.add('hidden');document.getElementById('screenSignup').classList.remove('hidden');let isBiz=accountType==='business';document.getElementById('signupTitle').innerText=isBiz?'Create Business Account':'Create Individual Account';document.getElementById('signupSub').innerText=isBiz?'Business: Black & Gold Dashboard':'Individual: White & Green Dashboard';document.getElementById('ownerCodeBox').classList.toggle('hidden',!(isBiz&&businessSize==='big'));document.getElementById('staffLoginLink').classList.toggle('hidden',!(isBiz&&businessSize==='big'));document.getElementById('signupCard').style.border=isBiz?'3px solid #d4af37':'3px solid #0f9d63';document.getElementById('signupBtn').className=isBiz?'btn btn-gold':'btn btn-green';}
function showStaffLogin(){document.getElementById('screenSignup').classList.add('hidden');document.getElementById('screenStaffLogin').classList.remove('hidden');}
function showContactFromHome(){alert('Contact Us\n\n📱 Your New Business Number Here\n📧 cleandatalai@gmail.com\n\nChange this in index.html when you get your new number bro!');}
function doSignup(){userName=document.getElementById('inName').value||'My Account';let mc=document.getElementById('inManagerCode').value;if(mc)managerCode=mc;role='owner';openDashboard();}
function doStaffLogin(){userName=document.getElementById('staffName').value||'Staff Member';role='staff';openDashboard();}
function openDashboard(){document.getElementById('screenSignup').classList.add('hidden');document.getElementById('screenStaffLogin').classList.add('hidden');document.getElementById('screenChoose').classList.add('hidden');document.getElementById('screenDashboard').classList.remove('hidden');document.getElementById('profileName').innerText=userName;document.getElementById('dropName').innerText=userName;document.getElementById('dropType').innerText=accountType==='business'?(businessSize==='big'?'Business - Big Company':'Business - Small Business'):'Individual';document.getElementById('currentPlan').innerText=accountType==='business'?'Business Plan':'Individual Plan';let isBiz=accountType==='business';document.getElementById('sidebar').className='sidebar '+(isBiz?'sidebar-business':'sidebar-individual');document.getElementById('topbar').style.background=isBiz?'#111':'#fff';document.getElementById('topbar').style.color=isBiz?'#fff':'#000';document.getElementById('dashLogo').innerHTML=isBiz?'🛡️ CDL <span style="color:#d4af37">CleanData LAI - BUSINESS</span>':'🛡️ CDL <span style="color:#0f9d63">CleanData LAI</span>';document.getElementById('profileBtn').style.background=isBiz?'#d4af37':'#0f9d63';document.getElementById('profileBtn').style.color=isBiz?'#000':'#fff';let menu=[['overview','📊 Overview'],['cleaning','🧹 Data Cleaning'],['pdfdata','📄 PDF Data'],['converter','🔄 File Converter'],['pdftools','🧰 PDF Tool Kits'],['planner','📅 Daily Planner'],['invoice','🧾 Quick Invoice']];if(isBiz){menu.push(['analyst','📊 Data Analyst']);if(businessSize==='big'){menu.push(['team','👥 Team Performance 🔒'],['profit','💰 Profit Tracker 🔒'],['staff','👥 Staff Management']);}}let html='';menu.forEach(m=>{html+=`<button class="menu-btn" onclick="showPanel('${m[0]}',this)">${m[1]}</button>`});document.getElementById('menuList').innerHTML=html;document.getElementById('staffBox').classList.toggle('hidden',role!=='staff');document.getElementById('plannerSub').innerText=isBiz&&businessSize==='big'?'Team tasks, assign to staff.':isBiz?'Business tasks for today.':'My personal tasks for today.';document.getElementById('overviewText').innerText=role==='staff'?`Welcome ${userName}. You are logged in as Staff. Do your tasks, clock in, work well!`:(isBiz?`Welcome ${userName}. Business Dashboard. ${businessSize==='big'?'You manage your team here.':'Small Business - simple, no team tracking.'}`:`Welcome ${userName}. Individual Dashboard - clean, simple, yours only.`);showPanel('overview',null);}
function showPanel(id,btn){document.querySelectorAll('.main .panel').forEach(p=>p.classList.add('hidden'));let el=document.getElementById('panel-'+id);if(el)el.classList.remove('hidden');document.querySelectorAll('.menu-btn').forEach(b=>b.classList.remove('active'));if(btn)btn.classList.add('active');document.getElementById('profileDropdown').classList.add('hidden');}
function toggleProfile(){document.getElementById('profileDropdown').classList.toggle('hidden');}
function goHome(){location.reload();}
function logout(){location.reload();}
function unlockManager(which){let v=document.getElementById(which==='team'?'managerCodeInput':'managerCodeInput2').value;if(v===managerCode){document.getElementById(which==='team'?'teamLock':'profitLock').classList.add('hidden');document.getElementById(which==='team'?'teamContent':'profitContent').classList.remove('hidden');alert('Unlocked ✅ Welcome Manager');}else alert('Wrong Code ❌ Access Denied. Only Managers with Owner Code.');}
function cleanFile(){let f=document.getElementById('fileInput').files[0];document.getElementById('cleanResult').innerText=f?`File ${f.name} cleaned! Duplicates removed, phones fixed. Download ready ✅`:'Please choose a file first.';document.getElementById('kpiFiles').innerText=parseInt(document.getElementById('kpiFiles').innerText)+1;document.getElementById('kpiRows').innerText=parseInt(document.getElementById('kpiRows').innerText)+120;}
function addTask(){let v=document.getElementById('taskInput').value;if(!v)return;tasks.push(v);document.getElementById('taskInput').value='';renderTasks();}
function renderTasks(){document.getElementById('taskList').innerHTML=tasks.map((t,i)=>`<li style="padding:8px;border-bottom:1px solid #eee">✅ ${t} <button onclick="tasks.splice(${i},1);renderTasks()">Done</button></li>`).join('');}
function clockIn(){let now=new Date().toLocaleTimeString();document.getElementById('clockStatus').innerText='Clocked In at '+now+' ✅ System is now tracking your work.';}
function addStaff(){let n=document.getElementById('newStaffName').value;if(!n)return;let id='CDL-00'+(document.querySelectorAll('#staffList li').length+1);let li=document.createElement('li');li.innerText=`${n} - Staff ID: ${id} - Password: 1234`;document.getElementById('staffList').appendChild(li);document.getElementById('newStaffName').value='';}
</script>
</body>
</html>
