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

// ─── PERSONA SWITCHER ───
function switchPersona(role) {
  const icons = {
    'Village Healthcare Worker': '🏥', 'Medicine Inventory Manager': '💊',
    'Distribution Planner': '📋', 'Transportation Coordinator': '🚚',
    'PHC Administrator': '🏛️', 'Rural Patient': '👤',
    'District Health Officer': '👨‍⚕️', 'Data Analyst': '📊',
    'Supply Chain Manager': '🔗', 'Emergency Coordinator': '🚨',
    'Government Inspector': '🏛️'
  };
  const iconEl = document.getElementById('persona-icon');
  const nameEl = document.getElementById('persona-name');
  if (iconEl) iconEl.textContent = icons[role] || '👤';
  if (nameEl) nameEl.textContent = role;
  
  fetch('/api/auth/switch-role', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role: role })
  })
  .then(res => res.json())
  .then(data => {
    if (data.success) {
      showToast('Role switched to ' + role, '👤');
      setTimeout(() => {
        // Reload current page, updating search params
        const url = new URL(window.location.href);
        url.searchParams.set('persona', role);
        window.location.href = url.toString();
      }, 500);
    }
  })
  .catch(() => {
    showToast('Role switched (local demo) to ' + role, '👤');
  });
}

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

// ─── LOAD ALERT COUNT ───
fetch('/api/shortage-alerts')
  .then(r => r.json())
  .then(data => {
    const el = document.getElementById('alert-count');
    const dot = document.getElementById('alert-dot');
    if (el) el.textContent = data.critical || 0;
    if (dot) dot.textContent = data.total || 0;
  })
  .catch(() => {});

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
async function logoutUser(e) {
  if (e) e.preventDefault();
  try {
    const res = await fetch('/api/auth/logout', { method: 'POST' });
    const d = await res.json();
    if (d.success) {
      showToast("Logged out successfully", "🔒");
      setTimeout(() => window.location.reload(), 800);
    }
  } catch (err) {
    console.error(err);
  }
}

// ─── DATA OBJECTS MODAL LOGIC ───
let currentModalData = [];
let currentModalType = '';

async function openDataObjectModal(type) {
  const modal = document.getElementById('data-object-modal');
  if (!modal) return;
  
  const iconEl = document.getElementById('dom-icon');
  const titleEl = document.getElementById('dom-title');
  const subtitleEl = document.getElementById('dom-subtitle');
  const tbody = document.getElementById('dom-tbody');
  const thead = document.getElementById('dom-thead');
  const countEl = document.getElementById('dom-count');
  const searchInput = document.getElementById('dom-search');
  
  if (searchInput) searchInput.value = '';
  currentModalType = type;
  currentModalData = [];
  
  modal.classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  
  tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:3rem;color:var(--text3)"><span class="spinner"></span> Fetching live data object records...</td></tr>';
  
  const config = {
    villages: { icon: '🏘️', title: 'Village Population Data Object', subtitle: 'System of Record: Flask | Mapped from Pega Blueprint', api: '/api/villages' },
    inventory: { icon: '💊', title: 'Medicine Inventory Data Object', subtitle: 'System of Record: Flask | Mapped from Pega Blueprint', api: '/api/inventory-audit' },
    consumption: { icon: '📋', title: 'Historical Consumption Records Data Object', subtitle: 'System of Record: Flask | Mapped from Pega Blueprint', api: '/api/demand-prediction' },
    outbreaks: { icon: '🦠', title: 'Disease Outbreak Report Data Object', subtitle: 'System of Record: Flask | Mapped from Pega Blueprint', api: '/api/raw/outbreaks' },
    weather: { icon: '🌤️', title: 'Weather Record Data Object', subtitle: 'System of Record: Flask | Mapped from Pega Blueprint', api: '/api/villages' },
    transport: { icon: '🚛', title: 'Transportation Resource Data Object', subtitle: 'System of Record: Flask | Mapped from Pega Blueprint', api: '/api/raw/transport' }
  };
  
  const current = config[type];
  if (!current) return;
  
  if (iconEl) iconEl.textContent = current.icon;
  if (titleEl) titleEl.textContent = current.title;
  if (subtitleEl) subtitleEl.textContent = current.subtitle;
  
  try {
    const res = await fetch(current.api);
    const data = await res.json();
    
    if (type === 'villages') {
      thead.innerHTML = '<tr><th>ID</th><th>Village Name</th><th>District</th><th>Population</th><th>Growth Rate</th><th>Age Group: 0-14</th><th>Age Group: 15-60</th><th>Age Group: 60+</th></tr>';
      currentModalData = data.map(v => ({
        id: v.id,
        name: v.name,
        district: v.district,
        population: v.population.toLocaleString('en-IN'),
        growth_rate: v.growth_rate + '%',
        age_0_14: v.age_distribution['0-14'] + '%',
        age_15_60: v.age_distribution['15-60'] + '%',
        age_60: v.age_distribution['60+'] + '%'
      }));
    } else if (type === 'inventory') {
      thead.innerHTML = '<tr><th>Village</th><th>Medicine</th><th>Category</th><th>Current Stock</th><th>Daily Usage</th><th>Days Remaining</th><th>Expiry Date</th><th>Status</th></tr>';
      const list = [];
      data.audit.forEach(v => {
        v.items.forEach(item => {
          list.push({
            village: v.village,
            medicine: item.medicine,
            category: item.category,
            stock: item.stock + ' units',
            daily: item.daily_consumption + ' units',
            days: item.days_remaining + ' days',
            expiry: item.expiry_date,
            status: item.status
          });
        });
      });
      currentModalData = list;
    } else if (type === 'consumption') {
      thead.innerHTML = '<tr><th>Village</th><th>Medicine</th><th>Category</th><th>Current Stock</th><th>Daily Usage</th><th>Predicted (7 Days)</th><th>Outbreak Factor</th><th>Weather Factor</th><th>Risk</th></tr>';
      currentModalData = data.predictions.map(p => ({
        village: p.village,
        medicine: p.medicine,
        category: p.category,
        stock: p.current_stock + ' units',
        daily: p.daily_consumption + ' units',
        predicted: p.predicted_demand + ' units',
        outbreak: p.outbreak_factor + 'x',
        weather: p.weather_factor + 'x',
        risk: p.risk
      }));
    } else if (type === 'outbreaks') {
      thead.innerHTML = '<tr><th>ID</th><th>Village</th><th>Disease</th><th>Affected Patients</th><th>Severity</th><th>Spread Rate</th><th>Date Started</th></tr>';
      currentModalData = data.map(o => {
        const villageNames = { V001: 'Raichur', V002: 'Gulbarga', V003: 'Koppal', V004: 'Bijapur', V005: 'Bellary', V006: 'Yadgir', V007: 'Dharwad', V008: 'Haveri' };
        return {
          id: o.id,
          village: villageNames[o.village_id] || o.village_id,
          disease: o.disease,
          affected: o.affected.toLocaleString('en-IN') + ' patients',
          severity: o.severity,
          spread: o.spread_rate + 'x/day',
          started: o.started
        };
      });
    } else if (type === 'weather') {
      thead.innerHTML = '<tr><th>Village</th><th>Temperature</th><th>Rainfall</th><th>Humidity</th><th>Active Alerts</th><th>Road Conditions</th></tr>';
      currentModalData = data.map(v => ({
        village: v.name,
        temp: v.weather.temp + '°C',
        rainfall: v.weather.rainfall + 'mm',
        humidity: v.weather.humidity + '%',
        alert: v.weather.alert || 'None',
        road: v.weather.road_condition
      }));
    } else if (type === 'transport') {
      thead.innerHTML = '<tr><th>ID</th><th>Type</th><th>Capacity</th><th>Available</th><th>Location</th><th>Status</th></tr>';
      currentModalData = data.map(t => ({
        id: t.id,
        type: t.type,
        capacity: t.capacity + ' units',
        available: t.available ? '🟢 Yes' : '🔴 No',
        location: t.location,
        status: t.status
      }));
    }
    
    renderDataObjectRows(currentModalData);
  } catch (err) {
    console.error(err);
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;padding:3rem;color:var(--red)">Failed to fetch live data object. Please ensure Flask app is running.</td></tr>';
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
  
  tbody.innerHTML = rows.map(row => {
    return `<tr>${Object.keys(row).map(key => {
      let val = row[key];
      let style = '';
      if (val === 'Critical' || val === '🔴 No') {
        style = 'color:var(--red);font-weight:700';
        val = `<span class="badge badge-critical">${val}</span>`;
      } else if (val === 'High' || val === 'Poor' || val === 'Flood Risk' || val === 'Heat Wave' || val === 'Heavy Rain') {
        style = 'color:var(--amber);font-weight:700';
        val = `<span class="badge badge-high">${val}</span>`;
      } else if (val === 'Medium' || val === 'Fair' || val === 'Flask Local') {
        style = 'color:var(--primary-l);font-weight:700';
        val = `<span class="badge badge-medium">${val}</span>`;
      } else if (val === 'Low' || val === 'Safe' || val === '🟢 Yes' || val === 'Good' || val === 'None') {
        style = 'color:var(--emerald);font-weight:700';
        if (val === 'Safe' || val === 'Low') val = `<span class="badge badge-low">${val}</span>`;
      }
      
      if (key === 'id') {
        style = 'font-family:"JetBrains Mono",monospace;color:var(--text3)';
      }
      
      return `<td style="${style}">${val}</td>`;
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

// Fetch alerts to populate notifications
async function loadNotifications() {
  const listEl = document.getElementById('notif-dropdown-list');
  const badgeCrit = document.getElementById('notif-badge-crit');
  if (!listEl) return;
  
  try {
    const res = await fetch('/api/shortage-alerts');
    const data = await res.json();
    const alerts = data.alerts || [];
    
    if (badgeCrit) badgeCrit.textContent = `${data.critical || 0} Critical`;
    
    if (alerts.length === 0) {
      listEl.innerHTML = '<div style="text-align:center;padding:2rem;color:var(--text3);font-size:.75rem">No active alerts. All stock safe!</div>';
      return;
    }
    
    listEl.innerHTML = alerts.slice(0, 4).map(alert => {
      let icon = '⚠️';
      if (alert.risk_level === 'Critical') icon = '🚨';
      else if (alert.outbreak_linked) icon = '🦠';
      
      return `
        <a href="/shortage" class="notif-item">
          <span class="notif-item-icon">${icon}</span>
          <div class="notif-item-content">
            <span class="notif-item-title">${alert.village}: ${alert.medicine}</span>
            <span class="notif-item-desc">Stock remaining: ${alert.current_stock} units. ${alert.action_required}</span>
            <span class="notif-item-time">Estimated stockout: ${alert.estimated_stockout}</span>
          </div>
        </a>
      `;
    }).join('');
  } catch(e) {
    console.error(e);
    listEl.innerHTML = '<div style="text-align:center;padding:1rem;color:var(--red);font-size:.72rem">Failed to load alerts.</div>';
  }
}


