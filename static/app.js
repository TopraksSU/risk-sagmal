const ids = ["saglik","beslenme","sut","ureme"];
let files = {};
let currentResult = null;
const analyzeBtn = document.querySelector("#analyzeBtn");
const clearBtn = document.querySelector("#clearBtn");
const fileStatus = document.querySelector("#fileStatus");
const errorBox = document.querySelector("#errorBox");
const loading = document.querySelector("#loading");
const results = document.querySelector("#results");

ids.forEach(id => {
  const input = document.querySelector(`#${id}`);
  input.addEventListener("change", () => {
    if (input.files?.[0]) {
      files[id] = input.files[0];
      input.closest(".upload-card").classList.add("ready");
      input.closest(".upload-card").querySelector("em").textContent = input.files[0].name;
    }
    const n = ids.filter(x => files[x]).length;
    fileStatus.textContent = n === 4 ? "4/4 dosya hazır." : `${n}/4 dosya seçildi.`;
    analyzeBtn.disabled = n !== 4;
  });
});

function fmt(v, digits=1){
  if(v === null || v === undefined || v === "") return "—";
  if(typeof v === "number") return new Intl.NumberFormat("tr-TR", {maximumFractionDigits:digits}).format(v);
  return v;
}
function riskClass(level){ return String(level || "").replaceAll(" ","-"); }
function tableHTML(rows, columns){
  let h = `<table class="mini-table"><thead><tr>${columns.map(c=>`<th>${c[0]}</th>`).join("")}</tr></thead><tbody>`;
  h += rows.map(r=>`<tr>${columns.map(c=>`<td>${fmt(r[c[1]], c[2] ?? 1)}</td>`).join("")}</tr>`).join("");
  return h + "</tbody></table>";
}

function render(data){
  const s = data.ozet;
  const kpis = [
    ["Analiz Edilen Hayvan", s["Analiz Edilen Hayvan"]],
    ["Laktasyondaki Hayvan", s["Laktasyondaki Hayvan"]],
    ["7 Günlük Süt Ort. (kg/gün)", s["7 Günlük Süt Ortalaması (kg/gün)"], ""],
    ["Yüksek Risk", s["V2 Yüksek Risk"], "risk-high"],
    ["Orta Risk", s["V2 Orta Risk"], "risk-medium"],
    ["İzle", s["V2 İzle"]],
    ["Gebe", (data.ureme.find(x=>x["Üreme Durumu"]==="Gebe")||{})["Hayvan Sayısı"] || 0],
    ["Tohumlu", (data.ureme.find(x=>x["Üreme Durumu"]==="Tohumlu")||{})["Hayvan Sayısı"] || 0],
    ["Aktiflik Verisi Olan", s["Aktiflik Verisi Olan"]],
    ["Meme Skoru Olan", s["Meme Skoru Olan"]],
    ["Robot Skoru Olan", s["Robot Skoru Olan"]],
    ["Son Tam Süt Günü", s["Trendde Kullanılan Son Tam Gün"]],
  ];
  document.querySelector("#kpis").innerHTML = kpis.map(x=>`<div class="kpi ${x[2]||""}"><span>${x[0]}</span><b>${fmt(x[1], x[0].includes("Süt Ort")?2:1)}</b></div>`).join("");
  document.querySelector("#reproTable").innerHTML = tableHTML(data.ureme, [["Durum","Üreme Durumu"],["Hayvan","Hayvan Sayısı",0]]);
  document.querySelector("#lactTable").innerHTML = tableHTML(data.laktasyon, [["Laktasyon","Laktasyon"],["Hayvan","Hayvan Sayısı",0],["Süt Verisi","Süt Verisi Olan Hayvan",0],["Ort. süt kg/gün","Ortalama Süt (kg/gün)",2]]);

  const cols = ["Hayvan No","V2 Genel Öncelik","V2 Seviye","Genel Sağlık Risk","Meme Sağlığı Risk","Sağım/Robot Risk","Üreme Durumu","Laktasyon No","Laktasyon Günü (DIM)","Süt 7 Gün Ort. (kg/gün)","V2 Açıklama"];
  document.querySelector("#riskTable thead").innerHTML = `<tr>${cols.map(c=>`<th>${c}</th>`).join("")}</tr>`;
  document.querySelector("#riskTable tbody").innerHTML = data.oncelikli_hayvanlar.map(r=>`<tr>${cols.map(c=>{
    if(c === "V2 Seviye") return `<td><span class="level ${riskClass(r[c])}">${r[c]}</span></td>`;
    return `<td>${fmt(r[c], c.includes("Risk")||c.includes("Öncelik")||c.includes("Süt 7")?1:0)}</td>`;
  }).join("")}</tr>`).join("");
  results.classList.remove("hidden");
  results.scrollIntoView({behavior:"smooth",block:"start"});
}

analyzeBtn.addEventListener("click", async () => {
  errorBox.classList.add("hidden"); results.classList.add("hidden"); loading.classList.remove("hidden");
  analyzeBtn.disabled = true;
  try{
    const payload = {};
    for(const id of ids) payload[id] = await files[id].text();
    const res = await fetch("/api/analiz", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail || "Analiz başarısız.");
    currentResult = data;
    render(data);
  }catch(err){
    currentResult = null;
    errorBox.textContent = err.message; errorBox.classList.remove("hidden");
  }finally{
    loading.classList.add("hidden"); analyzeBtn.disabled = ids.filter(x=>files[x]).length !== 4;
  }
});

async function downloadResult(kind){
  if(!currentResult) return;
  const res = await fetch(`/api/indir/${kind}`, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(currentResult)});
  if(!res.ok){
    const d = await res.json().catch(()=>({detail:"Dosya oluşturulamadı."}));
    errorBox.textContent=d.detail||"Dosya oluşturulamadı."; errorBox.classList.remove("hidden"); return;
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href=url; a.download=kind==="excel"?"suru_risk_analizi_v2.xlsx":"suru_risk_analizi_v2.csv";
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}
document.querySelector("#excelBtn").addEventListener("click",()=>downloadResult("excel"));
document.querySelector("#csvBtn").addEventListener("click",()=>downloadResult("csv"));

async function clearSession(show=true){
  currentResult = null;
  files = {};
  ids.forEach(id=>{
    const input=document.querySelector(`#${id}`); input.value="";
    const card=input.closest(".upload-card"); card.classList.remove("ready"); card.querySelector("em").textContent="CSV seç";
  });
  try{ await fetch("/api/oturum/sil", {method:"POST", keepalive:true}); }catch(e){}
  results.classList.add("hidden"); analyzeBtn.disabled=true;
  if(show) fileStatus.textContent = "Tarayıcı oturum verileri temizlendi.";
}
clearBtn.addEventListener("click", ()=>clearSession(true));
window.addEventListener("pagehide", () => { currentResult=null; files={}; });
