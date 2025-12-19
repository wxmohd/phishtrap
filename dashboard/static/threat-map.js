// ============================================
// THREAT MAP - Interactive Cyber Attack Visualization
// ============================================

// Country coordinates (approximate center points for visualization)
const COUNTRY_COORDS = {
  'BH': { x: 560, y: 280, name: 'Bahrain' },  // Target (center-right, middle)
  'FR': { x: 480, y: 220, name: 'France' },
  'US': { x: 200, y: 240, name: 'United States' },
  'CN': { x: 700, y: 260, name: 'China' },
  'RU': { x: 600, y: 180, name: 'Russia' },
  'DE': { x: 500, y: 210, name: 'Germany' },
  'GB': { x: 470, y: 210, name: 'United Kingdom' },
  'NL': { x: 490, y: 210, name: 'Netherlands' },
  'CA': { x: 220, y: 200, name: 'Canada' },
  'AU': { x: 750, y: 420, name: 'Australia' },
  'JP': { x: 760, y: 260, name: 'Japan' },
  'KR': { x: 730, y: 260, name: 'South Korea' },
  'IN': { x: 640, y: 300, name: 'India' },
  'BR': { x: 320, y: 400, name: 'Brazil' },
  'MX': { x: 180, y: 300, name: 'Mexico' },
  'IT': { x: 510, y: 240, name: 'Italy' },
  'ES': { x: 470, y: 250, name: 'Spain' },
  'SE': { x: 510, y: 190, name: 'Sweden' },
  'NO': { x: 500, y: 180, name: 'Norway' },
  'PL': { x: 520, y: 210, name: 'Poland' },
  'TR': { x: 540, y: 250, name: 'Turkey' },
  'SA': { x: 570, y: 300, name: 'Saudi Arabia' },
  'AE': { x: 580, y: 295, name: 'UAE' },
  'SG': { x: 680, y: 330, name: 'Singapore' },
  'HK': { x: 710, y: 290, name: 'Hong Kong' },
  'UNKNOWN': { x: 400, y: 300, name: 'Unknown' }
};

const TARGET_COORDS = COUNTRY_COORDS['BH'];

// View state
let currentView = 'map';
let currentThreatData = [];
let hoverCard = null;
let modal = null;

// Initialize threat map
function initThreatMap(threats) {
  currentThreatData = threats;
  
  // Create hover card
  hoverCard = document.createElement('div');
  hoverCard.className = 'threat-hover-card';
  document.body.appendChild(hoverCard);
  
  // Create modal
  createThreatModal();
  
  // Render map
  renderThreatMap();
}

// Create SVG map with threats
function renderThreatMap() {
  const container = document.getElementById('map-view');
  if (!container) return;
  
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'map-svg');
  svg.setAttribute('viewBox', '0 0 900 500');
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  
  // Background
  const bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  bg.setAttribute('width', '900');
  bg.setAttribute('height', '500');
  bg.setAttribute('fill', 'rgba(2, 6, 23, 0.3)');
  svg.appendChild(bg);
  
  // Simplified world map outline (continents as simple paths)
  const continents = [
    // North America
    'M 100,200 Q 150,180 200,190 L 250,200 Q 280,220 270,260 L 240,300 Q 200,320 160,300 L 120,260 Z',
    // South America
    'M 250,320 Q 280,340 290,380 L 310,440 Q 300,460 280,450 L 260,420 Q 240,380 250,340 Z',
    // Europe
    'M 450,180 Q 480,170 510,180 L 540,200 Q 550,220 540,240 L 510,250 Q 480,240 460,220 Z',
    // Africa
    'M 480,260 Q 520,270 540,300 L 550,360 Q 540,400 510,420 L 480,410 Q 460,380 470,340 L 480,300 Z',
    // Asia
    'M 560,160 Q 620,150 680,170 L 760,200 Q 800,240 790,280 L 760,300 Q 700,310 650,290 L 600,260 Q 570,220 560,180 Z',
    // Australia
    'M 720,380 Q 760,370 790,390 L 800,420 Q 790,440 760,440 L 730,430 Q 710,410 720,390 Z'
  ];
  
  continents.forEach(path => {
    const land = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    land.setAttribute('d', path);
    land.setAttribute('class', 'map-land');
    svg.appendChild(land);
  });
  
  // Draw threat arcs first (so they're behind markers)
  currentThreatData.forEach((threat, index) => {
    const sourceCoords = COUNTRY_COORDS[threat.country_code] || COUNTRY_COORDS['UNKNOWN'];
    drawThreatArc(svg, sourceCoords, TARGET_COORDS, threat, index);
  });
  
  // Draw target marker (Bahrain)
  const targetMarker = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  targetMarker.setAttribute('cx', TARGET_COORDS.x);
  targetMarker.setAttribute('cy', TARGET_COORDS.y);
  targetMarker.setAttribute('r', '8');
  targetMarker.setAttribute('class', 'target-marker');
  svg.appendChild(targetMarker);
  
  // Target label
  const targetLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  targetLabel.setAttribute('x', TARGET_COORDS.x);
  targetLabel.setAttribute('y', TARGET_COORDS.y - 15);
  targetLabel.setAttribute('text-anchor', 'middle');
  targetLabel.setAttribute('fill', '#EC4899');
  targetLabel.setAttribute('font-size', '12');
  targetLabel.setAttribute('font-weight', 'bold');
  targetLabel.textContent = '🇧🇭 Bahrain';
  svg.appendChild(targetLabel);
  
  // Draw attacker markers
  currentThreatData.forEach((threat, index) => {
    const sourceCoords = COUNTRY_COORDS[threat.country_code] || COUNTRY_COORDS['UNKNOWN'];
    drawAttackerMarker(svg, sourceCoords, threat, index);
  });
  
  container.innerHTML = '';
  container.appendChild(svg);
  
  // Add legend
  addMapLegend(container);
}

// Draw animated arc from attacker to target
function drawThreatArc(svg, source, target, threat, index) {
  const midX = (source.x + target.x) / 2;
  const midY = Math.min(source.y, target.y) - 80; // Arc height
  
  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  const d = `M ${source.x},${source.y} Q ${midX},${midY} ${target.x},${target.y}`;
  path.setAttribute('d', d);
  path.setAttribute('class', `threat-arc risk-${threat.risk_level}`);
  path.setAttribute('data-threat-index', index);
  path.style.animationDelay = `${index * 0.2}s`;
  
  path.addEventListener('mouseenter', (e) => showHoverCard(e, threat));
  path.addEventListener('mouseleave', hideHoverCard);
  path.addEventListener('click', () => showThreatModal(threat));
  
  svg.appendChild(path);
}

// Draw attacker marker
function drawAttackerMarker(svg, coords, threat, index) {
  const marker = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  marker.setAttribute('cx', coords.x);
  marker.setAttribute('cy', coords.y);
  marker.setAttribute('r', '6');
  marker.setAttribute('class', `attacker-marker risk-${threat.risk_level}`);
  marker.setAttribute('data-threat-index', index);
  
  marker.addEventListener('mouseenter', (e) => showHoverCard(e, threat));
  marker.addEventListener('mouseleave', hideHoverCard);
  marker.addEventListener('click', () => showThreatModal(threat));
  
  svg.appendChild(marker);
  
  // Country label
  const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  label.setAttribute('x', coords.x);
  label.setAttribute('y', coords.y - 12);
  label.setAttribute('text-anchor', 'middle');
  label.setAttribute('fill', '#94a3b8');
  label.setAttribute('font-size', '10');
  label.textContent = `${threat.country_flag || ''} ${threat.country_code || '??'}`;
  svg.appendChild(label);
}

// Show hover preview card
function showHoverCard(event, threat) {
  const brandIcon = getBrandIcon(threat.impersonated_brand);
  
  hoverCard.innerHTML = `
    <div class="brand-icon">${brandIcon}</div>
    <div class="brand-name">${threat.impersonated_brand || 'Unknown'}</div>
    <div class="campaign-id">Campaign #${(threat.campaign_id || 'unknown').substring(0, 6)}</div>
    <div class="risk-badge ${threat.risk_level}">${threat.risk_level.toUpperCase()} ${threat.risk_score || ''}</div>
  `;
  
  hoverCard.classList.add('show');
  updateHoverCardPosition(event);
}

// Update hover card position
function updateHoverCardPosition(event) {
  const x = event.clientX + 15;
  const y = event.clientY + 15;
  
  hoverCard.style.left = `${x}px`;
  hoverCard.style.top = `${y}px`;
}

// Hide hover card
function hideHoverCard() {
  hoverCard.classList.remove('show');
}

// Create threat detail modal
function createThreatModal() {
  modal = document.createElement('div');
  modal.className = 'threat-modal';
  modal.id = 'threat-modal';
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeThreatModal();
    }
  });
  
  document.body.appendChild(modal);
}

// Show threat detail modal
function showThreatModal(threat) {
  const brandIcon = getBrandIcon(threat.impersonated_brand);
  const verdict = threat.verdict || {};
  
  modal.innerHTML = `
    <div class="threat-modal-content">
      <button class="threat-modal-close" onclick="closeThreatModal()">×</button>
      
      <div class="threat-modal-header">
        <div class="threat-modal-icon">${brandIcon}</div>
        <div class="threat-modal-title">
          <div class="threat-modal-brand">${threat.impersonated_brand || 'Unknown Brand'}</div>
          <div class="threat-modal-campaign">Campaign #${(threat.campaign_id || 'unknown').substring(0, 6)}</div>
        </div>
        <div class="threat-modal-risk ${threat.risk_level}">
          ${threat.risk_level.toUpperCase()} ${threat.risk_score || ''}
        </div>
      </div>
      
      <div class="threat-modal-url">${threat.url}</div>
      
      <div class="threat-modal-chips">
        ${verdict.credential_harvest ? '<span class="threat-chip credential">🎣 Credential Harvest</span>' : ''}
        ${verdict.downloads_file ? '<span class="threat-chip download">📥 Downloads File</span>' : ''}
        ${verdict.redirects_to_legit ? '<span class="threat-chip redirect">✓ Redirects to Legit</span>' : ''}
      </div>
      
      <div class="threat-modal-meta">
        <div class="threat-meta-item">
          <span class="threat-meta-icon">${threat.country_flag || '🌐'}</span>
          <span>${threat.country_code || 'Unknown'}</span>
        </div>
        <div class="threat-meta-item">
          <span class="threat-meta-icon">📍</span>
          <span>IP ${threat.hosting_ip || 'N/A'}</span>
        </div>
        <div class="threat-meta-item">
          <span class="threat-meta-icon">🔗</span>
          <span>${threat.redirect_count || 0} redirect${threat.redirect_count > 1 ? 's' : ''}</span>
        </div>
        <div class="threat-meta-item">
          <span class="threat-meta-icon">🕒</span>
          <span>${threat.first_seen_time || 'N/A'}</span>
        </div>
      </div>
      
      <div class="threat-modal-actions">
        <a href="/sender_intelligence/${threat.email_id}" class="threat-action-btn primary">
          📧 View Email Details
        </a>
        <button class="threat-action-btn secondary" onclick="closeThreatModal()">
          Close
        </button>
      </div>
    </div>
  `;
  
  modal.classList.add('show');
}

// Close threat modal
function closeThreatModal() {
  modal.classList.remove('show');
}

// Get brand icon
function getBrandIcon(brand) {
  const icons = {
    'Microsoft': '🪟',
    'PayPal': '💳',
    'Amazon': '📦',
    'Apple': '🍎',
    'Google': '🔍',
    'Bank': '🏦'
  };
  return icons[brand] || '🌐';
}

// Add map legend
function addMapLegend(container) {
  const legend = document.createElement('div');
  legend.className = 'map-legend';
  legend.innerHTML = `
    <div class="map-legend-title">Risk Levels</div>
    <div class="map-legend-item">
      <div class="map-legend-dot high"></div>
      <span>High Risk</span>
    </div>
    <div class="map-legend-item">
      <div class="map-legend-dot medium"></div>
      <span>Medium Risk</span>
    </div>
    <div class="map-legend-item">
      <div class="map-legend-dot low"></div>
      <span>Low Risk</span>
    </div>
  `;
  container.appendChild(legend);
}

// Toggle between map and table view
function toggleView(view) {
  currentView = view;
  
  const mapView = document.getElementById('map-view');
  const tableView = document.getElementById('table-view');
  const mapBtn = document.getElementById('map-view-btn');
  const tableBtn = document.getElementById('table-view-btn');
  
  if (view === 'map') {
    mapView.style.display = 'block';
    tableView.style.display = 'none';
    mapBtn.classList.add('active');
    tableBtn.classList.remove('active');
    renderThreatMap();
  } else {
    mapView.style.display = 'none';
    tableView.style.display = 'block';
    mapBtn.classList.remove('active');
    tableBtn.classList.add('active');
  }
}

// Export functions for global access
window.initThreatMap = initThreatMap;
window.toggleView = toggleView;
window.closeThreatModal = closeThreatModal;
