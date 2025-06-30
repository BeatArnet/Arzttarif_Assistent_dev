const qcTranslations = {
    de: {title:'Qualitätskontrolle', testExample:'Beispiel testen', testAll:'Alle Beispiele testen', pass:'OK', fail:'Fehler'},
    fr: {title:'Contrôle de qualité', testExample:'Tester exemple', testAll:'Tester tous les exemples', pass:'OK', fail:'Erreur'},
    it: {title:'Controllo qualità', testExample:'Prova esempio', testAll:'Testa tutti gli esempi', pass:'OK', fail:'Errore'}
};
let examplesData = [];
let currentLang = 'de';

function applyLanguage(lang){
    currentLang = lang;
    const t = qcTranslations[lang];
    document.documentElement.lang = lang;
    document.getElementById('qcHeader').textContent = t.title;
    document.getElementById('testAllBtn').textContent = t.testAll;
    buildTable();
}

function loadExamples(){
    fetch('data/beispiele.json')
        .then(r=>r.json())
        .then(d=>{ examplesData=d; buildTable(); });
}

function buildTable(){
    const tbody = document.querySelector('#exampleTable tbody');
    if(!tbody || !examplesData.length) return;
    tbody.innerHTML='';
    const t = qcTranslations[currentLang];
    const shortKey = 'value_'+currentLang.toUpperCase();
    const extKey = 'extendedValue_'+currentLang.toUpperCase();
    for(let i=1;i<examplesData.length;i++){
        const ex=examplesData[i];
        const text=ex[extKey]||ex[shortKey]||'';
        const tr=document.createElement('tr');
        tr.innerHTML=`<td>${i}</td><td>${text}</td><td><button class="single-test" data-id="${i}">${t.testExample}</button></td><td id="res-${i}"></td>`;
        tbody.appendChild(tr);
    }
    document.querySelectorAll('.single-test').forEach(btn=>btn.addEventListener('click',()=>runTest(btn.dataset.id)));
}

function runTest(id){
    fetch('/api/test-example', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id:parseInt(id), lang: currentLang})})
        .then(r=>r.json()).then(res=>{
            const cell = document.getElementById('res-'+id);
            if(!cell) return;
            if(res.passed){
                cell.textContent = qcTranslations[currentLang].pass;
            }else{
                cell.textContent = qcTranslations[currentLang].fail + (res.diff ? ': '+res.diff : '');
            }
        }).catch(()=>{
            const cell=document.getElementById('res-'+id);
            if(cell) cell.textContent='error';
        });
}

function testAll(){
    for(let i=1;i<examplesData.length;i++) runTest(i);
}

document.getElementById('testAllBtn').addEventListener('click', testAll);

document.addEventListener('DOMContentLoaded', () => {
    const stored=localStorage.getItem('language');
    if(stored && ['de','fr','it'].includes(stored)) currentLang=stored;
    applyLanguage(currentLang);
    loadExamples();
});
