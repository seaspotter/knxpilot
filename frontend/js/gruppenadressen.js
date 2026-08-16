// ---------- Gruppenadressen (project sub-tab): GA tree preview / CSV export ----------
async function previewGA() {
  document.getElementById('gen-error').textContent = '';
  try {
    const data = await api(`/projects/${CURRENT_PROJECT}/preview`);
    const el = document.getElementById('ga-preview');
    el.innerHTML = data.main_groups.map(m => {
      const totalSubs = m.middles.reduce((sum, mid) => sum + mid.subs.length, 0);
      return `
      <details class="tree-main" open>
        <summary><span class="main">${m.main} ${m.name}</span> <span class="muted">(${totalSubs})</span></summary>
        ${m.middles.map(mid => `
          <details class="tree-middle">
            <summary><span class="middle">${m.main}/${mid.middle} ${mid.name}</span> <span class="muted">(${mid.subs.length})</span></summary>
            <div class="tree-subs">
              ${mid.subs.map(s => `
                <div class="tree-sub-row">
                  <span class="${s.name.endsWith('res') ? 'res' : 'sub'}">${m.main}/${mid.middle}/${s.sub} ${s.name}</span>${s.dpt ? ` <span class="addr">(${s.dpt})</span>` : ''}
                </div>`).join('')}
            </div>
          </details>`).join('')}
      </details>`;
    }).join('');
  } catch (e) {
    document.getElementById('gen-error').textContent = e.message;
  }
}

function expandAllGaTree(open) {
  document.querySelectorAll('#ga-preview details').forEach(d => { d.open = open; });
}

function downloadCSV() {
  window.location.href = `/api/projects/${CURRENT_PROJECT}/export.csv`;
}
