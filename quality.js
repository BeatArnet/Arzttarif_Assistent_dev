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
    fetch('data/baseline_results.json')
        .then(r=>r.json())
        .then(d=>{ examplesData=d; buildTable(); });
}

let totalTests = 0;
let passedTests = 0;

function buildTable(){
    const tbody = document.querySelector('#exampleTable tbody');
    if(!tbody || !Object.keys(examplesData).length) return;
    tbody.innerHTML='';
    const t = qcTranslations[currentLang]; // For button text, example text uses specific lang

    for(const [id, ex] of Object.entries(examplesData)){
        // Try to get example text in current language, fallback to DE, then first available
        let text = ex.query[currentLang] || ex.query['de'] || Object.values(ex.query)[0] || '';

        const tr=document.createElement('tr');
        tr.setAttribute('data-example-id', id);
        tr.innerHTML=`<td>${id}</td>
                      <td>${text}</td>
                      <td><button class="single-test-all-langs" data-id="${id}">${t.testExample}</button></td>
                      <td id="res-${id}-de"></td>
                      <td id="res-${id}-fr"></td>
                      <td id="res-${id}-it"></td>`;
        tbody.appendChild(tr);
    }
    document.querySelectorAll('.single-test-all-langs').forEach(btn => {
        btn.addEventListener('click', () => runTestsForRow(btn.dataset.id));
    });
    updateOverallSummary();
}

function runTest(id, lang) {
    return new Promise((resolve) => {
        const exampleId = parseInt(id);
        fetch('/api/test-example', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: exampleId, lang: lang })
        })
        .then(r => {
            if (!r.ok) {
                throw new Error(`HTTP error ${r.status}`);
            }
            return r.json();
        })
        .then(res => {
            const cell = document.getElementById(`res-${id}-${lang}`);
            if (!cell) {
                resolve({ id, lang, passed: false, error: 'Cell not found' });
                return;
            }
            if (res.passed) {
                cell.textContent = qcTranslations[currentLang].pass;
                cell.style.color = 'green';
                resolve({ id, lang, passed: true });
            } else {
                cell.textContent = qcTranslations[currentLang].fail + (res.diff ? ': ' + res.diff : '');
                cell.style.color = 'red';
                resolve({ id, lang, passed: false, diff: res.diff });
            }
        })
        .catch(error => {
            const cell = document.getElementById(`res-${id}-${lang}`);
            if (cell) {
                cell.textContent = 'error';
                cell.style.color = 'orange';
            }
            console.error(`Error testing example ${id} lang ${lang}:`, error);
            resolve({ id, lang, passed: false, error: error.message });
        });
    });
}

let testQueue = [];
let isTesting = false;

async function runTestsForRow(id) {
    testQueue.push(id);
    processTestQueue();
}

async function processTestQueue() {
    if (isTesting || testQueue.length === 0) {
        return;
    }
    isTesting = true;

    const id = testQueue.shift();

    const singleTestBtn = document.querySelector(`.single-test-all-langs[data-id="${id}"]`);
    if(singleTestBtn) singleTestBtn.disabled = true;

    // Clear previous results for this row
    document.getElementById(`res-${id}-de`).textContent = '...';
    document.getElementById(`res-${id}-fr`).textContent = '...';
    document.getElementById(`res-${id}-it`).textContent = '...';

    const langs = ['de', 'fr', 'it'];
    for (const lang of langs) {
        await runTest(id, lang); // Wait for each test to complete before starting the next
    }

    if(singleTestBtn) singleTestBtn.disabled = false;

    isTesting = false;
    processTestQueue();
}

async function testAll() {
    const testAllBtn = document.getElementById('testAllBtn');
    const singleTestBtns = document.querySelectorAll('.single-test-all-langs');

    testAllBtn.disabled = true;
    singleTestBtns.forEach(btn => btn.disabled = true);

    totalTests = 0;
    passedTests = 0;

    const exampleIds = Object.keys(examplesData);
    totalTests = exampleIds.length * 3;

    for (const exampleId of exampleIds) {
        await runTestsForRow(exampleId);
    }

    // After all tests are run, count the passed tests
    const results = document.querySelectorAll('td[id^="res-"]');
    passedTests = Array.from(results).filter(cell => cell.style.color === 'green').length;

    updateOverallSummary();

    testAllBtn.disabled = false;
    singleTestBtns.forEach(btn => btn.disabled = false);
}

function updateOverallSummary() {
    const summaryDiv = document.getElementById('overallSummary');
    if (totalTests > 0) {
        summaryDiv.textContent = `Gesamt: ${passedTests} / ${totalTests} bestanden.`;
    } else {
        summaryDiv.textContent = '';
    }
}

document.getElementById('testAllBtn').addEventListener('click', testAll);

document.addEventListener('DOMContentLoaded', () => {
    const stored=localStorage.getItem('language');
    if(stored && ['de','fr','it'].includes(stored)) currentLang=stored;
    applyLanguage(currentLang);
    loadExamples();
});
