'use strict';

// ─── THEME ───
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
  localStorage.setItem('medireach-theme', current === 'dark' ? 'light' : 'dark');
}
(function() {
  const saved = localStorage.getItem('medireach-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
})();

// ─── LIVE TIME ───
function updateTime() {
  const el = document.getElementById('topbar-time');
  if (!el) return;
  const now = new Date();
  el.textContent = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
}
setInterval(updateTime, 1000);
updateTime();

// ─── TOAST ───
function showToast(msg, icon) {
  const toast = document.getElementById('global-toast');
  if (!toast) return;
  const msgEl = document.getElementById('toast-msg');
  const iconEl = document.getElementById('toast-icon');
  if (msgEl) msgEl.textContent = msg;
  if (iconEl) iconEl.textContent = icon || '✅';
  toast.classList.remove('hidden');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => toast.classList.add('hidden'), 4000);
}

// ─── ANIMATED COUNTER ───
function animateCount(el, target, duration, suffix) {
  if (!el) return;
  const start = performance.now();
  const update = (now) => {
    const p = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - p, 3);
    const val = Math.round(target * eased);
    el.textContent = val.toLocaleString('en-IN') + (suffix || '');
    if (p < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

// ─── CHART DEFAULTS ───
if (typeof Chart !== 'undefined') {
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.font.size = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.padding = 10;
}

function getChartTheme() {
  const dark = document.documentElement.getAttribute('data-theme') !== 'light';
  return {
    grid: dark ? 'rgba(255,255,255,0.06)' : 'rgba(37,99,235,0.08)',
    text: dark ? '#94A3B8' : '#64748B',
    tooltipBg: dark ? 'rgba(15,23,42,0.95)' : 'rgba(255,255,255,0.95)',
    tooltipBorder: dark ? 'rgba(255,255,255,0.1)' : 'rgba(37,99,235,0.2)',
  };
}

// User logout handler
function logoutUser(e) {
  if (e) e.preventDefault();
  sessionStorage.clear();
  window.location.href = "index.html";
}

// ─── DATA OBJECTS MODAL LOGIC (GENERIC SUPABASE VIEWER) ───
let currentModalData = [];
let currentModalType = '';

async function openDataObjectModal(table) {
  if (typeof supabaseClient === 'undefined' || !supabaseClient) {
    showToast("Supabase client is not ready.", "🔴");
    return;
  }

  const modal = document.getElementById('data-object-modal');
  if (!modal) return;
  
  const iconEl = document.getElementById('dom-icon');
  const titleEl = document.getElementById('dom-title');
  const subtitleEl = document.getElementById('dom-subtitle');
  const tbody = document.getElementById('dom-tbody');
  const thead = document.getElementById('dom-thead');
  const searchInput = document.getElementById('dom-search');
  
  if (searchInput) searchInput.value = '';
  currentModalType = table;
  currentModalData = [];
  
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  
  tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:3rem;color:var(--text3)"><span class="spinner"></span> Querying Supabase table...</td></tr>';
  
  const config = {
    phcs: { icon: '🏘️', title: 'PHC Facilities Table', subtitle: 'Table: public.phcs | Mapped from Supabase System of Record' },
    inventory: { icon: '💊', title: 'Medicine Inventory Table', subtitle: 'Table: public.inventory | Mapped from Supabase System of Record' },
    patient_statistics: { icon: '📋', title: 'Patient Demographics Statistics Table', subtitle: 'Table: public.patient_statistics | Mapped from Supabase System of Record' },
    disease_outbreaks: { icon: '🦠', title: 'Disease Outbreak Reports Table', subtitle: 'Table: public.disease_outbreaks | Mapped from Supabase System of Record' },
    medicine_predictions: { icon: '📈', title: 'AI Demand Predictions Table', subtitle: 'Table: public.medicine_predictions | Mapped from Supabase System of Record' },
    medicine_shortages: { icon: '🚨', title: 'AI Shortage Alerts Table', subtitle: 'Table: public.medicine_shortages | Mapped from Supabase System of Record' },
    emergency_plans: { icon: '🚑', title: 'AI Active Emergency Dispatch Plans', subtitle: 'Table: public.emergency_plans | Mapped from Supabase System of Record' },
    medicine_transfers: { icon: '🔄', title: 'Medicine Redistribution transfers', subtitle: 'Table: public.medicine_transfers | Mapped from Supabase System of Record' }
  };
  
  const current = config[table];
  if (iconEl && current) iconEl.textContent = current.icon;
  if (titleEl && current) titleEl.textContent = current.title;
  if (subtitleEl && current) subtitleEl.textContent = current.subtitle;
  
  try {
    const { data, error } = await supabaseClient.from(table).select('*').limit(100);
    if (error) throw error;
    
    currentModalData = data || [];
    
    if (currentModalData.length > 0) {
      const keys = Object.keys(currentModalData[0]);
      thead.innerHTML = '<tr>' + keys.map(k => `<th>${k.replace('_', ' ').toUpperCase()}</th>`).join('') + '</tr>';
      renderDataObjectRows(currentModalData);
    } else {
      thead.innerHTML = '';
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:3rem;color:var(--text3)">No records found in this table.</td></tr>';
      const countEl = document.getElementById('dom-count');
      if (countEl) countEl.textContent = '0 records';
    }
  } catch (err) {
    console.error("Supabase DBO Fetch Error:", err);
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:3rem;color:var(--red)">Failed to fetch live data object records from Supabase.</td></tr>';
  }
}

function closeDataObjectModal() {
  const modal = document.getElementById('data-object-modal');
  if (modal) modal.classList.add('hidden');
  document.body.style.overflow = '';
}

function renderDataObjectRows(rows) {
  const tbody = document.getElementById('dom-tbody');
  const countEl = document.getElementById('dom-count');
  if (!tbody) return;
  
  if (countEl) countEl.textContent = rows.length + ' records';
  
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:2rem;color:var(--text3)">No matching records found.</td></tr>';
    return;
  }
  
  const keys = Object.keys(rows[0]);
  
  tbody.innerHTML = rows.map(row => {
    return `<tr>${keys.map(key => {
      let val = row[key];
      let style = '';
      
      if (typeof val === 'object' && val !== null) {
        val = JSON.stringify(val);
      }
      
      if (val === 'Critical' || val === '🔴 No') {
        style = 'color:var(--red);font-weight:700';
        val = `<span class="badge badge-critical">${val}</span>`;
      } else if (val === 'High' || val === 'Poor' || val === 'Flood Risk' || val === 'Heat Wave' || val === 'Heavy Rain') {
        style = 'color:var(--amber);font-weight:700';
        val = `<span class="badge badge-high">${val}</span>`;
      } else if (val === 'Medium' || val === 'Fair') {
        style = 'color:var(--primary-l);font-weight:700';
        val = `<span class="badge badge-medium">${val}</span>`;
      } else if (val === 'Low' || val === 'Safe' || val === '🟢 Yes' || val === 'Good' || val === 'None') {
        style = 'color:var(--emerald);font-weight:700';
        if (val === 'Safe' || val === 'Low') val = `<span class="badge badge-low">${val}</span>`;
      }
      
      if (key === 'id') {
        style = 'font-family:"JetBrains Mono",monospace;color:var(--text3)';
      }
      
      return `<td style="${style}">${val === null ? '—' : val}</td>`;
    }).join('')}</tr>`;
  }).join('');
}

function filterDataObjectTable() {
  const query = document.getElementById('dom-search').value.toLowerCase();
  if (!query) {
    renderDataObjectRows(currentModalData);
    return;
  }
  
  const filtered = currentModalData.filter(row => {
    return Object.values(row).some(val => String(val).toLowerCase().includes(query));
  });
  
  renderDataObjectRows(filtered);
}

// Toggle Notification Dropdown
function toggleNotificationDropdown(e) {
  if (e) e.stopPropagation();
  const dropdown = document.getElementById('notif-dropdown');
  if (!dropdown) return;
  
  const isHidden = dropdown.classList.contains('hidden');
  
  if (isHidden) {
    dropdown.classList.remove('hidden');
    loadNotifications();
  } else {
    dropdown.classList.add('hidden');
  }
}

// Close notifications when clicking elsewhere
document.addEventListener('click', (e) => {
  const dropdown = document.getElementById('notif-dropdown');
  const trigger = document.querySelector('.topbar-notif');
  if (dropdown && !dropdown.classList.contains('hidden')) {
    if (!dropdown.contains(e.target) && (!trigger || !trigger.contains(e.target))) {
      dropdown.classList.add('hidden');
    }
  }
});

// Fetch alerts to populate notifications (directly from Supabase state)
function loadNotifications() {
  const listEl = document.getElementById('notif-dropdown-list');
  const badgeCrit = document.getElementById('notif-badge-crit');
  if (!listEl) return;
  
  // Use global shortages array populated in dashboard
  const alerts = shortages || [];
  const critCount = shortages.filter(s => s.risk_level === 'Critical').length;
  
  if (badgeCrit) badgeCrit.textContent = `${critCount} Critical`;
  
  if (alerts.length === 0) {
    listEl.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text3);font-size:.75rem">No active alerts. All stock safe!</div>';
    return;
  }
  
  listEl.innerHTML = alerts.slice(0, 5).map(alert => {
    let icon = '⚠️';
    if (alert.risk_level === 'Critical') icon = '🚨';
    
    return `
      <div class="notif-item">
        <span class="notif-item-icon">${icon}</span>
        <div class="notif-item-content">
          <span class="notif-item-title">${alert.phc_id}: ${alert.medicine_name}</span>
          <span class="notif-item-desc">Stock remaining: ${alert.current_stock}. Daily consumption: ${alert.daily_consumption}.</span>
          <span class="notif-item-time">Estimated stockout: ${alert.estimated_stockout} (${alert.days_remaining} days left)</span>
        </div>
      </div>
    `;
  }).join('');
}
