/**
 * THREAT INTELLIGENCE GLOBE - 3D Visualization
 * Three.js powered interactive globe with cyber/neon aesthetic
 */

// Globe configuration
const GLOBE_CONFIG = {
  radius: 100,
  segments: 48, // Reduced from 64 for better performance
  bahrain: { lat: 26.0667, lon: 50.5577 }, // Bahrain coordinates
  cameraDistance: 300,
  autoRotateSpeed: 0.3,
  arcHeight: 0.4,
  arcSegments: 40, // Reduced from 50 for better performance
  maxThreats: 50,
  colors: {
    high: 0xef4444,    // Red
    medium: 0xf59e0b,  // Yellow
    low: 0x10b981,     // Green
    globe: 0x1e293b,   // Dark blue-gray
    gridLines: 0xEC4899, // Pink
    atmosphere: 0xA855F7  // Purple
  }
};

// Global state
let scene, camera, renderer, globe, controls;
let threatArcs = [];
let selectedThreat = null;
let threatData = [];
let animationId = null;

/**
 * Initialize the 3D globe
 */
function initThreatGlobe(data) {
  console.log('[GLOBE] Starting initialization...');
  
  // Check for Three.js
  if (typeof THREE === 'undefined') {
    console.error('[GLOBE] THREE.js not loaded');
    return;
  }
  
  // Check for OrbitControls
  if (typeof THREE.OrbitControls === 'undefined') {
    console.error('[GLOBE] OrbitControls not loaded');
    const loading = document.querySelector('.globe-loading');
    if (loading) {
      loading.innerHTML = '<p style="color: #ef4444;">3D controls not available. Please refresh.</p>';
    }
    return;
  }
  
  threatData = data.slice(0, GLOBE_CONFIG.maxThreats); // Limit to top 50
  console.log('[GLOBE] Processing', threatData.length, 'threats');
  
  const container = document.querySelector('.globe-canvas-wrapper');
  if (!container) {
    console.error('[GLOBE] Container not found');
    return;
  }
  
  console.log('[GLOBE] Container found, dimensions:', container.clientWidth, 'x', container.clientHeight);

  // Setup scene
  scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x0f172a, 400, 800);

  // Setup camera
  camera = new THREE.PerspectiveCamera(
    45,
    container.clientWidth / container.clientHeight,
    1,
    2000
  );
  
  // Position camera to focus on Bahrain
  const bahrainPos = latLonToVector3(
    GLOBE_CONFIG.bahrain.lat,
    GLOBE_CONFIG.bahrain.lon,
    GLOBE_CONFIG.cameraDistance
  );
  camera.position.set(bahrainPos.x * 1.5, bahrainPos.y * 1.5, bahrainPos.z * 1.5);
  camera.lookAt(0, 0, 0);

  // Setup renderer
  renderer = new THREE.WebGLRenderer({
    canvas: document.getElementById('threat-globe-canvas'),
    antialias: true,
    alpha: true
  });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(window.devicePixelRatio);
  renderer.setClearColor(0x0f172a, 1);

  // Setup controls
  try {
    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.25; // Higher = less slippery, more responsive
    controls.rotateSpeed = 0.5; // Slower rotation for better control
    controls.minDistance = 120; // Closer zoom for tiny Bahrain!
    controls.maxDistance = 500;
    controls.autoRotate = false; // Disabled auto-rotation
    controls.autoRotateSpeed = 0;
    console.log('[GLOBE] OrbitControls initialized successfully');
  } catch (error) {
    console.error('[GLOBE] Failed to initialize OrbitControls:', error);
    const loading = document.querySelector('.globe-loading');
    if (loading) {
      loading.innerHTML = '<p style="color: #ef4444;">Failed to initialize 3D controls: ' + error.message + '</p>';
    }
    return;
  }

  // Add lights
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambientLight);

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.6);
  directionalLight.position.set(200, 200, 200);
  scene.add(directionalLight);

  // Hide loading state immediately (globe will render with fallback color)
  const loading = document.querySelector('.globe-loading');
  if (loading) loading.style.display = 'none';

  // Create globe
  createGlobe();

  // Create threat arcs
  createThreatArcs();

  // Add atmosphere glow
  createAtmosphere();

  // Start animation
  animate();

  // Handle window resize
  window.addEventListener('resize', onWindowResize);

  // Setup raycaster for interactions
  setupInteractions();

  // Update stats
  updateGlobeStats();

  console.log('[GLOBE] Initialized with', threatData.length, 'threats');
}

/**
 * Create the cyber/neon styled globe
 */
function createGlobe() {
  const geometry = new THREE.SphereGeometry(
    GLOBE_CONFIG.radius,
    GLOBE_CONFIG.segments,
    GLOBE_CONFIG.segments
  );

  // Create material with fallback color (shows immediately)
  const material = new THREE.MeshPhongMaterial({
    color: 0x1e3a5f, // Dark blue fallback
    emissive: 0x112244,
    emissiveIntensity: 0.1,
    shininess: 15,
    transparent: false,
    opacity: 1.0
  });

  globe = new THREE.Mesh(geometry, material);
  scene.add(globe);

  // Load Earth texture asynchronously (doesn't block rendering)
  const textureLoader = new THREE.TextureLoader();
  textureLoader.load(
    'https://unpkg.com/three-globe@2.24.11/example/img/earth-blue-marble.jpg',
    function(texture) {
      console.log('[GLOBE] Earth texture loaded');
      // Apply texture once loaded
      material.map = texture;
      material.color.setHex(0x8899bb); // Slight blue tint
      material.needsUpdate = true;
    },
    undefined,
    function(err) {
      console.error('[GLOBE] Failed to load Earth texture:', err);
      // Keep fallback color if texture fails
    }
  );

  // Add subtle grid lines for cyber aesthetic overlay
  createGridLines();

  // Mark Bahrain location
  createLocationMarker(
    GLOBE_CONFIG.bahrain.lat,
    GLOBE_CONFIG.bahrain.lon,
    0xEC4899, // Pink
    1.5
  );
}

/**
 * Create cyber grid lines on globe
 */
function createGridLines() {
  const gridMaterial = new THREE.LineBasicMaterial({
    color: 0x00ffff, // Cyan for cyber aesthetic
    transparent: true,
    opacity: 0.03, // Very subtle, even when zoomed
    linewidth: 0.3 // Much skinnier lines
  });

  // Longitude lines only (vertical lines) - fewer lines for performance
  for (let lon = 0; lon < 360; lon += 30) { // Changed from 20 to 30 degrees
    const points = [];
    for (let lat = -90; lat <= 90; lat += 10) { // Changed from 5 to 10 degrees
      const pos = latLonToVector3(lat, lon, GLOBE_CONFIG.radius + 0.5);
      points.push(pos);
    }
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const line = new THREE.Line(geometry, gridMaterial);
    globe.add(line);
  }
}

/**
 * Create atmosphere glow effect
 */
function createAtmosphere() {
  const geometry = new THREE.SphereGeometry(
    GLOBE_CONFIG.radius * 1.15,
    GLOBE_CONFIG.segments,
    GLOBE_CONFIG.segments
  );

  const material = new THREE.ShaderMaterial({
    vertexShader: `
      varying vec3 vNormal;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      varying vec3 vNormal;
      void main() {
        float intensity = pow(0.6 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
        gl_FragColor = vec4(0.66, 0.33, 0.97, 1.0) * intensity;
      }
    `,
    side: THREE.BackSide,
    blending: THREE.AdditiveBlending,
    transparent: true
  });

  const atmosphere = new THREE.Mesh(geometry, material);
  scene.add(atmosphere);
}

/**
 * Create location marker (for Bahrain and threat origins)
 */
function createLocationMarker(lat, lon, color, size = 1) {
  const geometry = new THREE.SphereGeometry(size, 16, 16);
  const material = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.8
  });

  const marker = new THREE.Mesh(geometry, material);
  const pos = latLonToVector3(lat, lon, GLOBE_CONFIG.radius + 1);
  marker.position.copy(pos);

  // Add glow
  const glowGeometry = new THREE.SphereGeometry(size * 2, 16, 16);
  const glowMaterial = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.3,
    side: THREE.BackSide
  });
  const glow = new THREE.Mesh(glowGeometry, glowMaterial);
  marker.add(glow);

  globe.add(marker);
  return marker;
}

/**
 * Create threat arcs from origins to Bahrain
 */
function createThreatArcs() {
  threatArcs = [];
  let skippedCount = 0;
  let unknownCountries = [];
  let countryCount = {}; // Track how many threats per country
  let countryOffsets = {}; // Track offset for each country

  threatData.forEach((threat, index) => {
    // Determine country code - prioritize sender_intel, fallback to link country_code
    let countryCode = threat.country_code;
    
    // If country_code is XX or missing, try sender_intel
    if (!countryCode || countryCode === 'XX') {
      if (threat.sender_intel && threat.sender_intel.country) {
        // Use country name to derive code (simplified - just use first 2 letters uppercase)
        const country = threat.sender_intel.country.toUpperCase();
        // Try to map common countries
        const countryMap = {
          'UNITED STATES': 'US',
          'UNITED KINGDOM': 'GB',
          'RUSSIA': 'RU',
          'CHINA': 'CN',
          'GERMANY': 'DE',
          'FRANCE': 'FR',
          'INDIA': 'IN',
          'BRAZIL': 'BR',
          'CANADA': 'CA',
          'AUSTRALIA': 'AU'
        };
        countryCode = countryMap[country] || country.substring(0, 2);
      }
    }
    
    // If still no valid country code, skip this threat
    if (!countryCode || countryCode === 'XX') {
      console.log('[GLOBE] Skipping threat - no valid country code:', threat);
      skippedCount++;
      return;
    }

    // Track country occurrences
    countryCount[countryCode] = (countryCount[countryCode] || 0) + 1;

    // Get approximate country coordinates
    let originCoords = getCountryCoordinates(countryCode);
    
    // If country not in our list, use a fallback location (random point)
    if (!originCoords) {
      console.log('[GLOBE] Unknown country code:', countryCode, '- using fallback coordinates');
      unknownCountries.push(countryCode);
      
      // Generate random coordinates as fallback
      const randomLat = (Math.random() * 160) - 80; // -80 to 80
      const randomLon = (Math.random() * 360) - 180; // -180 to 180
      originCoords = { lat: randomLat, lon: randomLon };
    }

    // Add slight offset for multiple threats from same country
    const offset = countryOffsets[countryCode] || 0;
    countryOffsets[countryCode] = offset + 1;
    
    const offsetLat = originCoords.lat + (offset * 2); // 2 degree offset
    const offsetLon = originCoords.lon + (offset * 2);

    // Create arc
    const arc = createPulsingArc(
      offsetLat,
      offsetLon,
      GLOBE_CONFIG.bahrain.lat,
      GLOBE_CONFIG.bahrain.lon,
      threat.risk_level,
      threat
    );

    if (arc) {
      threatArcs.push(arc);
      globe.add(arc.mesh);

      // Add origin marker (only once per country)
      if (offset === 0) {
        const color = getRiskColor(threat.risk_level);
        createLocationMarker(originCoords.lat, originCoords.lon, color, 0.8);
      }
    }
  });

  console.log('[GLOBE] Created', threatArcs.length, 'threat arcs');
  console.log('[GLOBE] Skipped', skippedCount, 'threats (no country code)');
  console.log('[GLOBE] Threats per country:', countryCount);
  
  // Log detailed breakdown for countries with multiple threats
  Object.keys(countryCount).forEach(country => {
    if (countryCount[country] > 1) {
      const threatsFromCountry = threatData.filter(t => t.country_code === country);
      console.log(`[GLOBE] ${country} has ${countryCount[country]} threats:`);
      threatsFromCountry.forEach((t, idx) => {
        console.log(`  ${idx + 1}. Time: ${t.first_seen_time} | Email: ${t.email_subject} | URL: ${t.url.substring(0, 50)}...`);
      });
    }
  });
  
  if (unknownCountries.length > 0) {
    console.log('[GLOBE] Unknown countries (using fallback):', [...new Set(unknownCountries)].join(', '));
  }
}

/**
 * Create pulsing wave arc between two points
 */
function createPulsingArc(lat1, lon1, lat2, lon2, riskLevel, threatInfo) {
  const start = latLonToVector3(lat1, lon1, GLOBE_CONFIG.radius);
  const end = latLonToVector3(lat2, lon2, GLOBE_CONFIG.radius);

  // Calculate arc control point (raised above surface)
  const distance = start.distanceTo(end);
  const mid = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
  const height = distance * GLOBE_CONFIG.arcHeight;
  mid.normalize().multiplyScalar(GLOBE_CONFIG.radius + height);

  // Create curve
  const curve = new THREE.QuadraticBezierCurve3(start, mid, end);
  const points = curve.getPoints(GLOBE_CONFIG.arcSegments);

  // Create tube geometry for the arc
  const tubeGeometry = new THREE.TubeGeometry(
    curve,
    50, // segments
    0.8, // radius (thickness) - balanced for visibility
    8,  // radial segments
    false
  );

  // Get color based on risk
  const color = getRiskColor(riskLevel);

  // Create material with pulsing effect
  const material = new THREE.MeshBasicMaterial({
    color: color,
    transparent: true,
    opacity: 0.85, // Increased opacity for better visibility
    side: THREE.DoubleSide
  });

  const arc = new THREE.Mesh(tubeGeometry, material);

  // Store metadata
  arc.userData = {
    threat: threatInfo,
    baseOpacity: 0.6,
    pulsePhase: Math.random() * Math.PI * 2, // Random start phase
    color: color,
    highlighted: false
  };

  return {
    mesh: arc,
    curve: curve,
    points: points
  };
}

/**
 * Get color based on risk level
 */
function getRiskColor(riskLevel) {
  switch (riskLevel) {
    case 'high':
      return GLOBE_CONFIG.colors.high;
    case 'medium':
      return GLOBE_CONFIG.colors.medium;
    case 'low':
      return GLOBE_CONFIG.colors.low;
    default:
      return GLOBE_CONFIG.colors.medium;
  }
}

/**
 * Convert lat/lon to 3D vector
 */
function latLonToVector3(lat, lon, radius) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);

  const x = -(radius * Math.sin(phi) * Math.cos(theta));
  const y = radius * Math.cos(phi);
  const z = radius * Math.sin(phi) * Math.sin(theta);

  return new THREE.Vector3(x, y, z);
}

/**
 * Get approximate country coordinates
 */
function getCountryCoordinates(countryCode) {
  const coords = {
    'RU': { lat: 61.5240, lon: 105.3188 },
    'CN': { lat: 35.8617, lon: 104.1954 },
    'US': { lat: 37.0902, lon: -95.7129 },
    'NL': { lat: 52.1326, lon: 5.2913 },
    'FR': { lat: 46.2276, lon: 2.2137 },
    'DE': { lat: 51.1657, lon: 10.4515 },
    'GB': { lat: 55.3781, lon: -3.4360 },
    'IN': { lat: 20.5937, lon: 78.9629 },
    'BR': { lat: -14.2350, lon: -51.9253 },
    'AU': { lat: -25.2744, lon: 133.7751 },
    'CA': { lat: 56.1304, lon: -106.3468 },
    'JP': { lat: 36.2048, lon: 138.2529 },
    'KR': { lat: 35.9078, lon: 127.7669 },
    'IT': { lat: 41.8719, lon: 12.5674 },
    'ES': { lat: 40.4637, lon: -3.7492 },
    'MX': { lat: 23.6345, lon: -102.5528 },
    'ZA': { lat: -30.5595, lon: 22.9375 },
    'AR': { lat: -38.4161, lon: -63.6167 },
    'SE': { lat: 60.1282, lon: 18.6435 },
    'NO': { lat: 60.4720, lon: 8.4689 },
    'PL': { lat: 51.9194, lon: 19.1451 },
    'TR': { lat: 38.9637, lon: 35.2433 },
    'SA': { lat: 23.8859, lon: 45.0792 },
    'AE': { lat: 23.4241, lon: 53.8478 },
    'EG': { lat: 26.8206, lon: 30.8025 },
    'NG': { lat: 9.0820, lon: 8.6753 },
    'KE': { lat: -0.0236, lon: 37.9062 },
    'ID': { lat: -0.7893, lon: 113.9213 },
    'MY': { lat: 4.2105, lon: 101.9758 },
    'SG': { lat: 1.3521, lon: 103.8198 },
    'TH': { lat: 15.8700, lon: 100.9925 },
    'VN': { lat: 14.0583, lon: 108.2772 },
    'PH': { lat: 12.8797, lon: 121.7740 },
    'PK': { lat: 30.3753, lon: 69.3451 },
    'BD': { lat: 23.6850, lon: 90.3563 },
    'IR': { lat: 32.4279, lon: 53.6880 },
    'IQ': { lat: 33.2232, lon: 43.6793 },
    'IL': { lat: 31.0461, lon: 34.8516 },
    'UA': { lat: 48.3794, lon: 31.1656 },
    'RO': { lat: 45.9432, lon: 24.9668 },
    'GR': { lat: 39.0742, lon: 21.8243 },
    'PT': { lat: 39.3999, lon: -8.2245 },
    'BE': { lat: 50.5039, lon: 4.4699 },
    'CH': { lat: 46.8182, lon: 8.2275 },
    'AT': { lat: 47.5162, lon: 14.5501 },
    'CZ': { lat: 49.8175, lon: 15.4730 },
    'HU': { lat: 47.1625, lon: 19.5033 },
    'FI': { lat: 61.9241, lon: 25.7482 },
    'DK': { lat: 56.2639, lon: 9.5018 },
    'IE': { lat: 53.4129, lon: -8.2439 },
    'NZ': { lat: -40.9006, lon: 174.8860 }
  };

  return coords[countryCode] || null;
}

/**
 * Animation loop
 */
function animate() {
  // Only animate if:
  // 1. Page/tab is visible (not minimized or switched away)
  // 2. Threat Intelligence tab is currently active
  const threatIntelTab = document.getElementById('threat-intel-tab');
  const isTabActive = threatIntelTab && threatIntelTab.classList.contains('active');
  const isPageVisible = !document.hidden;
  
  if (!isTabActive || !isPageVisible) {
    // Pause animation to save CPU/GPU when not viewing globe
    animationId = requestAnimationFrame(animate);
    return;
  }

  animationId = requestAnimationFrame(animate);

  // Update controls
  controls.update();

  // Animate pulsing arcs
  const time = Date.now() * 0.001;
  threatArcs.forEach(arc => {
    if (!arc.mesh.userData.highlighted) {
      const phase = arc.mesh.userData.pulsePhase;
      const pulse = Math.sin(time * 2 + phase) * 0.3 + 0.7;
      arc.mesh.material.opacity = arc.mesh.userData.baseOpacity * pulse;
    }
  });

  // Render scene
  renderer.render(scene, camera);
}

/**
 * Handle window resize
 */
function onWindowResize() {
  const container = document.querySelector('.globe-canvas-wrapper');
  if (!container) return;

  camera.aspect = container.clientWidth / container.clientHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(container.clientWidth, container.clientHeight);
}

/**
 * Setup mouse interactions (click, hover)
 */
function setupInteractions() {
  const canvas = document.getElementById('threat-globe-canvas');
  const raycaster = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let hoveredArc = null;
  
  // Create tooltip element
  let tooltip = document.getElementById('globe-tooltip');
  if (!tooltip) {
    tooltip = document.createElement('div');
    tooltip.id = 'globe-tooltip';
    tooltip.style.cssText = `
      position: absolute;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid #ec4899;
      border-radius: 8px;
      padding: 12px 16px;
      color: #fff;
      font-size: 13px;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.2s;
      z-index: 10000;
      box-shadow: 0 4px 20px rgba(236, 72, 153, 0.3);
      max-width: 250px;
    `;
    document.body.appendChild(tooltip);
  }

  // Mouse move for hover
  canvas.addEventListener('mousemove', (event) => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    // Check intersections with arcs
    const arcMeshes = threatArcs.map(a => a.mesh);
    const intersects = raycaster.intersectObjects(arcMeshes);

    if (intersects.length > 0) {
      const intersectedArc = intersects[0].object;

      if (hoveredArc && hoveredArc !== intersectedArc) {
        hoveredArc.userData.highlighted = false;
        hoveredArc.material.opacity = hoveredArc.userData.baseOpacity;
      }

      // Highlight this arc
      intersectedArc.userData.highlighted = true;
      intersectedArc.material.opacity = 1.0;

      // Dim other arcs
      threatArcs.forEach(arc => {
        if (arc.mesh !== intersectedArc) {
          arc.mesh.material.opacity = 0.2;
        }
      });

      // Show tooltip
      const threat = intersectedArc.userData.threat;
      const country = getCountryName(threat.country_code);
      tooltip.innerHTML = `
        <div style="font-weight: 600; color: #ec4899; font-size: 14px;">
          ${threat.country_flag} ${country}
        </div>
        <div style="font-size: 12px; color: #94a3b8; margin-top: 4px;">
          ⏰ ${threat.first_seen_time || 'Unknown time'}
        </div>
      `;
      tooltip.style.left = event.clientX + 15 + 'px';
      tooltip.style.top = event.clientY + 15 + 'px';
      tooltip.style.opacity = '1';

      // Change cursor
      canvas.style.cursor = 'pointer';
    } else {
      // Reset all arcs
      if (hoveredArc) {
        hoveredArc.userData.highlighted = false;
        hoveredArc = null;
      }

      threatArcs.forEach(arc => {
        arc.mesh.userData.highlighted = false;
        arc.mesh.material.opacity = arc.mesh.userData.baseOpacity;
      });
      
      // Hide tooltip
      tooltip.style.opacity = '0';

      canvas.style.cursor = 'grab';
    }
  });

  // Click to select threat
  canvas.addEventListener('click', (event) => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);

    const arcMeshes = threatArcs.map(a => a.mesh);
    const intersects = raycaster.intersectObjects(arcMeshes);

    if (intersects.length > 0) {
      const threat = intersects[0].object.userData.threat;
      selectThreat(threat);
    }
  });
}

/**
 * Select a threat and show intel panel
 */
function selectThreat(threat) {
  selectedThreat = threat;
  console.log('[GLOBE] Selected threat:', threat);

  // Update intel panel
  updateIntelPanel(threat);

  // Stop auto-rotation temporarily
  controls.autoRotate = false;
  setTimeout(() => {
    controls.autoRotate = true;
  }, 5000);
}

/**
 * Update intelligence panel with threat details
 */
function updateIntelPanel(threat) {
  const content = document.querySelector('.intel-panel-content');
  if (!content) return;

  // Show loading
  content.innerHTML = `
    <div class="intel-loading">
      <div class="intel-loading-spinner"></div>
      <p>Analyzing threat...</p>
    </div>
  `;

  // Simulate API delay (replace with actual API calls)
  setTimeout(() => {
    content.innerHTML = generateIntelHTML(threat);
  }, 500);
}

/**
 * Generate HTML for intel panel
 */
function generateIntelHTML(threat) {
  const brandIcon = getBrandIcon(threat.impersonated_brand);
  const riskClass = threat.risk_level || 'medium';

  return `
    <div class="threat-detail-card">
      <div class="threat-detail-header">
        <div class="threat-brand">
          <span class="threat-brand-icon">${brandIcon}</span>
          <span>${threat.impersonated_brand || 'Unknown'}</span>
        </div>
        <span class="threat-risk-badge ${riskClass}">
          ${riskClass.toUpperCase()} ${threat.risk_score || ''}
        </span>
      </div>

      <div class="threat-url">${threat.url}</div>

      <div class="threat-meta">
        <span class="threat-meta-item">
          ${threat.country_flag || '🌐'} 
          ${threat.sender_intel?.country || threat.country_code || 'Unknown'}
          ${threat.sender_intel?.city ? `, ${threat.sender_intel.city}` : ''}
        </span>
        ${(threat.sender_ip || threat.hosting_ip) ? `<span class="threat-meta-item">📍 ${threat.sender_ip || threat.hosting_ip}</span>` : ''}
        ${threat.campaign_id ? `<span class="threat-meta-item">🎯 Campaign #${threat.campaign_id.substring(0, 6)}</span>` : ''}
        ${threat.first_seen_time ? `<span class="threat-meta-item">🕒 ${threat.first_seen_time}</span>` : ''}
      </div>
    </div>

    ${generateExternalIntelHTML(threat)}
    ${generateMitreAttackHTML(threat)}
    ${generateInfrastructureHTML(threat)}
    ${generateActionsHTML(threat)}
  `;
}

/**
 * Generate external threat intel section
 */
function generateExternalIntelHTML(threat) {
  const intel = threat.sender_intel || {};
  
  // Only show if we have real data
  if (!intel.phishtank_listed && !intel.urlhaus_listed && !intel.virustotal_detections && !intel.abuse_score) {
    return '';
  }
  
  return `
    <div class="intel-section">
      <h3 class="intel-section-title">
        <span class="intel-section-icon">🔍</span>
        External Threat Intelligence
      </h3>

      ${intel.phishtank_listed ? `
      <div class="intel-item">
        <div class="intel-item-header">
          <span class="intel-item-label">PhishTank</span>
          <span class="intel-item-status detected">⚠️ Verified Phish</span>
        </div>
        <div class="intel-item-value">
          URL confirmed as active phishing site in PhishTank database.
        </div>
      </div>
      ` : ''}

      ${intel.urlhaus_listed ? `
      <div class="intel-item">
        <div class="intel-item-header">
          <span class="intel-item-label">URLhaus</span>
          <span class="intel-item-status detected">🚨 Malware Detected</span>
        </div>
        <div class="intel-item-value">
          URL listed in URLhaus malware database.
        </div>
      </div>
      ` : ''}

      ${intel.virustotal_detections ? `
      <div class="intel-item">
        <div class="intel-item-header">
          <span class="intel-item-label">VirusTotal</span>
          <span class="intel-item-status ${intel.virustotal_detections >= 5 ? 'detected' : 'warning'}">
            ${intel.virustotal_detections}/92 Vendors
          </span>
        </div>
        <div class="intel-item-value">
          ${intel.virustotal_detections} security vendors flagged this as malicious.
        </div>
      </div>
      ` : ''}

      ${intel.abuse_score ? `
      <div class="intel-item">
        <div class="intel-item-header">
          <span class="intel-item-label">AbuseIPDB</span>
          <span class="intel-item-status ${intel.abuse_score >= 75 ? 'detected' : 'warning'}">
            ${intel.abuse_score}% Confidence
          </span>
        </div>
        <div class="intel-item-value">
          IP has abuse confidence score of ${intel.abuse_score}%.
        </div>
      </div>
      ` : ''}
    </div>
  `;
}

/**
 * Generate MITRE ATT&CK techniques section
 */
function generateMitreAttackHTML(threat) {
  const intel = threat.sender_intel || {};
  const riskFactors = intel.risk_factors ? JSON.parse(intel.risk_factors) : [];
  
  // Map risk factors to MITRE techniques
  const techniques = [];
  
  // Always show phishing if it's a phishing email
  if (threat.risk_level === 'high' || intel.phishtank_listed) {
    techniques.push({
      id: 'T1566.002',
      name: 'Phishing: Spearphishing Link'
    });
  }
  
  // Credential harvesting
  if (riskFactors.some(f => f.toLowerCase().includes('credential'))) {
    techniques.push({
      id: 'T1598.003',
      name: 'Phishing for Information: Credential Phishing'
    });
  }
  
  // Malware delivery
  if (intel.urlhaus_listed) {
    techniques.push({
      id: 'T1566.001',
      name: 'Phishing: Spearphishing Attachment'
    });
  }
  
  // VPN/Proxy evasion
  if (intel.is_vpn || intel.is_proxy || intel.is_tor) {
    techniques.push({
      id: 'T1090',
      name: 'Proxy: Multi-hop Proxy'
    });
  }
  
  // Only show if we have techniques
  if (techniques.length === 0) {
    return '';
  }
  
  return `
    <div class="intel-section">
      <h3 class="intel-section-title">
        <span class="intel-section-icon">🎯</span>
        MITRE ATT&CK Techniques
      </h3>

      ${techniques.map(t => `
      <div class="mitre-technique">
        <span class="mitre-technique-id">${t.id}</span>
        <span class="mitre-technique-name">${t.name}</span>
      </div>
      `).join('')}
    </div>
  `;
}

/**
 * Generate infrastructure section
 */
function generateInfrastructureHTML(threat) {
  // Prioritize sender_ip over hosting_ip
  const ipAddress = threat.sender_ip || threat.hosting_ip;
  const intel = threat.sender_intel || {};
  
  // Only show section if we have data
  if (!ipAddress && !threat.redirect_count && !intel.isp && !intel.asn) {
    return '';
  }
  
  return `
    <div class="intel-section">
      <h3 class="intel-section-title">
        <span class="intel-section-icon">🌐</span>
        Infrastructure
      </h3>

      ${ipAddress ? `
      <div class="intel-item">
        <div class="intel-item-header">
          <span class="intel-item-label">Sender IP Address</span>
          ${(intel.is_vpn || intel.is_proxy || intel.is_tor) ? `
            <span class="intel-item-status warning">
              ${intel.is_tor ? '🧅 Tor' : intel.is_vpn ? '🔒 VPN' : '🔀 Proxy'}
            </span>
          ` : ''}
        </div>
        <div class="intel-item-value">
          ${ipAddress}
        </div>
      </div>
      ` : ''}

      ${intel.isp ? `
      <div class="intel-item">
        <div class="intel-item-header">
          <span class="intel-item-label">ISP / Hosting</span>
        </div>
        <div class="intel-item-value">
          ${intel.isp}${intel.asn ? ` (${intel.asn})` : ''}
        </div>
      </div>
      ` : ''}

      ${threat.redirect_count ? `
      <div class="intel-item">
        <div class="intel-item-header">
          <span class="intel-item-label">Redirects</span>
        </div>
        <div class="intel-item-value">
          ${threat.redirect_count} redirect${threat.redirect_count > 1 ? 's' : ''} detected
        </div>
      </div>
      ` : ''}
    </div>
  `;
}

/**
 * Generate action buttons
 */
function generateActionsHTML(threat) {
  return `
    <div class="intel-actions">
      <button class="intel-action-btn primary" onclick="viewEmailDetails(${threat.email_id})">
        📧 View Email
      </button>
      <button class="intel-action-btn secondary" onclick="exportThreatIOCs()">
        📤 Export IOCs
      </button>
    </div>
  `;
}

/**
 * Get brand icon emoji
 */
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

/**
 * Update globe statistics overlay
 */
function updateGlobeStats() {
  // Count visible arcs only
  const visibleThreats = threatArcs.filter(arc => arc.mesh.visible).map(arc => arc.threat);
  
  const stats = {
    total: visibleThreats.length,
    high: visibleThreats.filter(t => t.risk_level === 'high').length,
    medium: visibleThreats.filter(t => t.risk_level === 'medium').length,
    low: visibleThreats.filter(t => t.risk_level === 'low').length
  };

  const overlay = document.querySelector('.globe-stats-overlay');
  if (overlay) {
    overlay.innerHTML = `
      <div class="globe-stat-item">
        <span class="globe-stat-label">Total Threats:</span>
        <span class="globe-stat-value">${stats.total}</span>
      </div>
      <div class="globe-stat-item">
        <span class="globe-stat-label">High Risk:</span>
        <span class="globe-stat-badge high">${stats.high}</span>
      </div>
      <div class="globe-stat-item">
        <span class="globe-stat-label">Medium Risk:</span>
        <span class="globe-stat-badge medium">${stats.medium}</span>
      </div>
      <div class="globe-stat-item">
        <span class="globe-stat-label">Low Risk:</span>
        <span class="globe-stat-badge low">${stats.low}</span>
      </div>
    `;
  }
}

/**
 * View email details (redirect to AI reply page)
 */
function viewEmailDetails(emailId) {
  window.location.href = `/ai-reply/${emailId}`;
}

/**
 * Export threat IOCs
 */
function exportThreatIOCs() {
  if (!selectedThreat) return;

  const iocs = {
    url: selectedThreat.url,
    ip: selectedThreat.hosting_ip,
    country: selectedThreat.country_code,
    risk_level: selectedThreat.risk_level,
    risk_score: selectedThreat.risk_score,
    campaign_id: selectedThreat.campaign_id,
    timestamp: new Date().toISOString()
  };

  const blob = new Blob([JSON.stringify(iocs, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `threat-iocs-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Get country name from country code
 */
function getCountryName(code) {
  const countries = {
    'US': 'United States', 'CN': 'China', 'RU': 'Russia', 'DE': 'Germany',
    'GB': 'United Kingdom', 'FR': 'France', 'IN': 'India', 'BR': 'Brazil',
    'CA': 'Canada', 'AU': 'Australia', 'JP': 'Japan', 'KR': 'South Korea',
    'IT': 'Italy', 'ES': 'Spain', 'MX': 'Mexico', 'NL': 'Netherlands',
    'SE': 'Sweden', 'PL': 'Poland', 'TR': 'Turkey', 'ID': 'Indonesia',
    'SA': 'Saudi Arabia', 'AE': 'UAE', 'BH': 'Bahrain', 'KW': 'Kuwait',
    'QA': 'Qatar', 'OM': 'Oman', 'EG': 'Egypt', 'ZA': 'South Africa',
    'NG': 'Nigeria', 'KE': 'Kenya', 'AR': 'Argentina', 'CL': 'Chile',
    'CO': 'Colombia', 'PE': 'Peru', 'VE': 'Venezuela', 'UA': 'Ukraine',
    'RO': 'Romania', 'CZ': 'Czech Republic', 'BE': 'Belgium', 'AT': 'Austria',
    'CH': 'Switzerland', 'DK': 'Denmark', 'FI': 'Finland', 'NO': 'Norway',
    'IE': 'Ireland', 'PT': 'Portugal', 'GR': 'Greece', 'HU': 'Hungary',
    'NZ': 'New Zealand', 'SG': 'Singapore', 'MY': 'Malaysia', 'TH': 'Thailand',
    'VN': 'Vietnam', 'PH': 'Philippines', 'PK': 'Pakistan', 'BD': 'Bangladesh',
    'IL': 'Israel', 'IQ': 'Iraq', 'IR': 'Iran', 'JO': 'Jordan', 'LB': 'Lebanon',
    'SY': 'Syria', 'YE': 'Yemen', 'LY': 'Libya', 'DZ': 'Algeria', 'MA': 'Morocco',
    'TN': 'Tunisia', 'SD': 'Sudan', 'ET': 'Ethiopia', 'GH': 'Ghana'
  };
  return countries[code] || code || 'Unknown';
}

/**
 * Get color for risk level
 */
function getRiskColor(riskLevel) {
  const colors = {
    'high': '#ef4444',
    'medium': '#f59e0b',
    'low': '#10b981'
  };
  return colors[riskLevel] || colors['medium'];
}

/**
 * Filter threats by time range
 */
window.filterGlobeThreats = function(filter) {
  console.log('[GLOBE] Filtering threats:', filter);
  
  if (!threatData || threatData.length === 0) {
    console.log('[GLOBE] No threat data to filter');
    return;
  }
  
  const now = new Date();
  let cutoffDate;
  
  // Calculate cutoff date
  switch(filter) {
    case '24h':
      cutoffDate = new Date(now - 24 * 60 * 60 * 1000);
      break;
    case '7d':
      cutoffDate = new Date(now - 7 * 24 * 60 * 60 * 1000);
      break;
    case '30d':
      cutoffDate = new Date(now - 30 * 24 * 60 * 60 * 1000);
      break;
    case 'all':
      cutoffDate = null;
      break;
  }
  
  console.log(`[GLOBE] Time filter: ${filter}, Cutoff: ${cutoffDate ? cutoffDate.toISOString() : 'none'}, Now: ${now.toISOString()}`);
  
  // Filter threat arcs
  let visibleCount = 0;
  let hiddenCount = 0;
  threatArcs.forEach(arc => {
    const threat = arc.threat;
    if (!cutoffDate) {
      // Show all
      arc.mesh.visible = true;
      visibleCount++;
    } else {
      // Check threat date
      if (threat.received_at) {
        const threatDate = new Date(threat.received_at);
        if (threatDate >= cutoffDate) {
          arc.mesh.visible = true;
          visibleCount++;
        } else {
          arc.mesh.visible = false;
          hiddenCount++;
        }
      } else {
        // If no date, hide it
        arc.mesh.visible = false;
        hiddenCount++;
        console.warn('[GLOBE] Threat missing received_at:', threat.email_subject);
      }
    }
  });
  
  console.log(`[GLOBE] Filter result: ${visibleCount} visible, ${hiddenCount} hidden`);
  
  console.log(`[GLOBE] Showing ${visibleCount} of ${threatArcs.length} threats`);
  
  // Update stats overlay
  updateGlobeStats();
};

/**
 * Cleanup on page unload
 */
window.addEventListener('beforeunload', () => {
  if (animationId) {
    cancelAnimationFrame(animationId);
  }
  if (renderer) {
    renderer.dispose();
  }
});
