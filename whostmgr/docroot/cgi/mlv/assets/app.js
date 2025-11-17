(() => {
  const state = {
    logs: [],
    filtered: [],
    selectedId: null,
    expandedCategories: new Set(), // Guardar categorías expandidas
    liveMode: false,
    liveInterval: null,
    lastLineCount: 0,
    showAllLogs: false,
    compressedActive: false,
    updateInProgress: false,
  };

  const dictionary = {
    'tooltip.live_default': 'Auto-refresh every 5 seconds',
    'tooltip.pause_live': 'Pause auto-refresh',
    'tooltip.refresh_default': 'Search in log',
    'tooltip.refresh_compressed': 'Download the compressed file to review it',
    'tooltip.live_compressed': 'Not available for compressed logs',
    'compressed.notice': 'Log "{{name}}" is compressed. Download it to review ({{path}}).',
    'compressed.placeholder': '(This log is compressed. Use the download option to review it).',
    'compressed.title': 'Compressed log',
    'compressed.text': 'Download the file to review it locally.',
    'button.download': 'Download file',
    'button.search': 'Search',
    'button.search_all': 'Search all',
    'button.live': 'Live',
    'button.pause': 'Pause',
    'button.update': 'Update Plugin',
    'button.update_highlight': '✨ Update to v{{version}}',
    'button.update_now': 'Update Now',
    'button.cancel': 'Cancel',
    'button.close': 'Close',
    'input.filter.placeholder': 'Filter by name',
    'input.filter.clear_title': 'Clear search',
    'input.lines.label': 'Last lines:',
    'input.search.label': 'Search:',
    'input.search.placeholder': 'Expression or text',
    'input.search.clear_title': 'Clear search',
    'input.case.label': 'Case sensitive',
    'viewer.initial': 'Select a log to begin.',
    'viewer.not_found': 'Log not found in the list.',
    'viewer.no_results': '(No results)',
    'viewer.no_matches_file': '(No matches found in the file)',
    'viewer.no_matches_configured': '(No matches in the configured logs)',
    'viewer.no_matching_lines': '(No matching lines available)',
    'list.not_found': 'Not found',
    'badge.compressed': 'Compressed',
    'status.loading_logs': 'Loading log list…',
    'status.fetch_list_failed': 'Unable to obtain the log list',
    'status.no_logs_configured': 'No configured logs found. Check log_sources.json',
    'status.no_logs_entries': 'No logs configured',
    'status.warning_missing_logs': 'Warning: None of the configured logs exist on the server',
    'status.logs_found': 'Found {{found}} of {{total}} logs available',
    'status.error_loading_logs': 'Error loading logs: {{error}}',
    'status.error_loading_logs_list': 'Error: {{error}}',
    'status.update_in_progress_logs': 'Update in progress. Wait until it finishes to view logs.',
    'status.log_compressed': 'This log is compressed. Use the download option to review it.',
    'status.searching_full': 'Searching entire file…',
    'status.reading_log': 'Reading log…',
    'status.error_reading_log': 'Error reading log',
    'status.search_done_zero': 'Search completed: 0 matches',
    'status.search_done': 'Search: {{count}} match(es) found',
    'status.showing_lines': 'Showing {{count}} line(s)',
    'status.live_updated': 'Live: {{count}} line(s) - updated',
    'status.update_in_progress_search': 'Update in progress. Search once it finishes.',
    'status.enter_text_all': 'Enter text to search all logs',
    'status.searching_all': 'Searching matches in all logs…',
    'status.error_search_all': 'Error performing the global search',
    'status.global_matches_zero': 'Global search: 0 matches',
    'status.global_matches': 'Global search: {{count}} match(es)',
    'status.update_in_progress_wait': 'Update in progress. Wait until it finishes.',
    'status.update_in_progress_live': 'Live mode is disabled during the update.',
    'status.select_log_live': 'Select a log to enable live mode',
    'status.live_not_available_compressed': 'Live mode is not available for compressed logs.',
    'status.live_not_available_search': 'Live mode is not available when a search is active',
    'status.live_started': 'Live mode enabled - refreshing every 5 seconds',
    'status.live_paused': 'Live mode paused',
    'notification.console_hint': 'Check the browser console (F12) for more details',
    'update.status.current': 'Current version: {{current}}',
    'update.status.available': ' | Available version: {{remote}}',
    'update.status.failed': 'Could not verify the version',
    'update.status.unknown': 'Unknown',
    'update.progress.downloading': 'Downloading update...',
    'update.progress.done': '✓ Update completed. Reloading page...',
    'update.error.prefix': '✗ Error:',
    'update.error.details': 'Details:',
    'update.error.debug': 'Debug:',
    'update.error.exit_code': 'Exit code: {{code}}',
    'update.error.unknown': 'Unknown error',
    'update.notification.title': '✨ New version available: v{{version}}',
    'update.notification.subtitle': 'Click to update',
    'error.invalid_json': 'Server response is invalid (corrupted JSON).',
    'category.cpanel': 'cPanel',
    'category.web_server': 'Web Server',
    'category.mail': 'Mail',
    'category.security': 'Security',
    'category.database': 'Database',
    'category.system': 'System',
    'category.other': 'Other'
  };
  const translate = (key, vars = {}) => {
    let text = dictionary[key];
    if (typeof text !== 'string') {
      return key;
    }
    return text.replace(/\{\{(\w+)\}\}/g, (match, name) => {
      if (Object.prototype.hasOwnProperty.call(vars, name)) {
        return String(vars[name]);
      }
      return match;
    });
  };

  const translateCategory = (category) => {
    if (!category) {
      const fallback = dictionary['category.other'];
      return typeof fallback === 'string' ? fallback : 'Other';
    }
    const slug = category.toLowerCase().replace(/[^a-z0-9]+/g, '_');
    const key = `category.${slug}`;
    const value = dictionary[key];
    if (typeof value === 'string') {
      return value;
    }
    return category;
  };

  const elements = {
    list: document.getElementById('logs'),
    filter: document.getElementById('filter-input'),
    filterClearBtn: document.getElementById('filter-clear-btn'),
    lines: document.getElementById('lines-input'),
    search: document.getElementById('search-input'),
    caseCheckbox: document.getElementById('case-checkbox'),
    refreshBtn: document.getElementById('refresh-btn'),
    liveBtn: document.getElementById('live-btn'),
    pauseBtn: document.getElementById('pause-btn'),
    searchAllBtn: document.getElementById('search-all-btn'),
    clearSearchBtn: document.getElementById('clear-search-btn'),
    output: document.getElementById('log-output'),
    status: document.getElementById('status'),
    template: document.getElementById('log-item-template'),
    compressedBanner: document.getElementById('compressed-banner'),
    compressedText: document.getElementById('compressed-text'),
    downloadCompressedBtn: document.getElementById('download-compressed-btn'),
  };

  if (elements.liveBtn) {
    elements.liveBtn.title = translate('tooltip.live_default');
  }
  if (elements.pauseBtn) {
    elements.pauseBtn.title = translate('tooltip.pause_live');
  }
  if (elements.refreshBtn) {
    elements.refreshBtn.title = translate('tooltip.refresh_default');
  }

  // Obtener la URL base del script actual
  const getBaseUrl = () => {
    // Debug: Log información del icono
    console.log('[ICON DEBUG] window.MLV_BASE:', window.MLV_BASE);
    console.log('[ICON DEBUG] window.location:', window.location.href);
    console.log('[ICON DEBUG] document.location:', document.location.href);
    
    // Usar la variable global si está disponible (inyectada por el servidor)
    if (window.MLV_BASE) {
      const base = window.MLV_BASE.endsWith('/') 
        ? window.MLV_BASE 
        : window.MLV_BASE + '/';
      return base;
    }
    // Fallback: obtener del script actual y subir un nivel (de assets/ a mlv/)
    const script = document.currentScript || document.querySelector('script[src*="app.js"]');
    if (script && script.src) {
      const url = new URL(script.src, window.location.href);
      // Remover /assets/app.js y dejar solo el directorio base
      const path = url.pathname.replace(/\/assets\/[^/]+$/, '/');
      return path;
    }
    // Fallback final: usar la ruta actual y subir un nivel si estamos en assets/
    let path = window.location.pathname;
    if (path.includes('/assets/')) {
      path = path.substring(0, path.indexOf('/assets/') + 1);
    } else {
      path = path.substring(0, path.lastIndexOf('/') + 1);
    }
    return path;
  };

  const baseUrl = getBaseUrl();

  const fetchJSON = async (url) => {
    try {
      const fullUrl = url.startsWith('http') ? url : baseUrl + url;
      const response = await fetch(fullUrl, {
        credentials: 'same-origin',
        headers: {
          'Accept': 'application/json',
        },
      });

      const contentType = response.headers.get('content-type') || '';
      const rawText = await response.text();

      console.log('[FETCH]', url, 'status:', response.status, 'content-type:', contentType);
      console.log('[FETCH] raw:', rawText.substring(0, 200));

      if (!contentType.includes('application/json')) {
        const message = rawText && rawText.trim() ? rawText.trim() : `HTTP ${response.status}`;
        throw new Error(message);
      }

      if (!response.ok) {
        let payload;
        try {
          payload = JSON.parse(rawText);
        } catch {
          payload = { message: rawText || `HTTP ${response.status}` };
        }
        throw new Error(payload.message || payload.detail || `HTTP ${response.status}`);
      }

      try {
        return JSON.parse(rawText);
      } catch (parseError) {
        console.error('[FETCH] Error al parsear JSON:', parseError, 'Respuesta cruda:', rawText);
        throw new Error(translate('error.invalid_json'));
      }
    } catch (error) {
      console.error('Error en fetchJSON:', error, 'URL:', url);
      throw error;
    }
  };

  const setStatus = (message, type = 'info') => {
    elements.status.textContent = message || '';
    elements.status.className = type;
  };

  const setStatusKey = (key, type = 'info', vars = {}) => {
    setStatus(translate(key, vars), type);
  };

  const isCompressedLog = (log) => Boolean(log && (log.compressed === true || log.compressed === 'true'));

  const setCompressedControls = (disabled) => {
    const toggle = (el, value) => {
      if (!el) return;
      el.disabled = value;
    };

    toggle(elements.refreshBtn, disabled);
    toggle(elements.liveBtn, disabled);
    toggle(elements.pauseBtn, disabled);
    toggle(elements.search, disabled);
    toggle(elements.searchAllBtn, disabled);
    toggle(elements.lines, disabled);
    toggle(elements.caseCheckbox, disabled);

    if (!disabled && state.liveMode) {
      // Mantener los controles deshabilitados que controla el modo live
      elements.refreshBtn.disabled = true;
      elements.search.disabled = true;
    }
  };

  const showCompressedNotice = (log) => {
    if (!elements.compressedBanner || !log) return;

    stopLiveMode();
    state.compressedActive = true;
    elements.compressedBanner.style.display = 'flex';
    if (elements.compressedText) {
      elements.compressedText.textContent = translate('compressed.notice', {
        name: log.name,
        path: log.path,
      });
    }
    if (elements.downloadCompressedBtn) {
      elements.downloadCompressedBtn.disabled = false;
      elements.downloadCompressedBtn.dataset.logId = log.id;
    }

    if (elements.liveBtn) {
      elements.liveBtn.title = translate('tooltip.live_compressed');
    }

    if (elements.refreshBtn) {
      elements.refreshBtn.title = translate('tooltip.refresh_compressed');
    }

    if (elements.clearSearchBtn) {
      elements.clearSearchBtn.style.display = 'none';
    }

    setCompressedControls(true);
    elements.output.textContent = translate('compressed.placeholder');
  };

  const hideCompressedNotice = () => {
    if (!elements.compressedBanner) return;

    state.compressedActive = false;
    elements.compressedBanner.style.display = 'none';
    if (elements.compressedText) {
      elements.compressedText.textContent = '';
    }
    if (elements.downloadCompressedBtn) {
      elements.downloadCompressedBtn.disabled = true;
      delete elements.downloadCompressedBtn.dataset.logId;
    }

    if (elements.liveBtn) {
      elements.liveBtn.title = translate('tooltip.live_default');
    }

    if (elements.refreshBtn) {
      elements.refreshBtn.title = translate('tooltip.refresh_default');
    }

    setCompressedControls(false);
  };

  const renderList = () => {
    elements.list.innerHTML = '';
    const fragment = document.createDocumentFragment();

    const hasFilter = elements.filter.value.trim().length > 0;
    
    // Agrupar logs por categoría
    const logsByCategory = {};
    state.filtered.forEach(log => {
      const category = log.category || 'Other';
      if (!logsByCategory[category]) {
        logsByCategory[category] = { exists: [], missing: [] };
      }
      if (log.exists) {
        logsByCategory[category].exists.push(log);
      } else {
        logsByCategory[category].missing.push(log);
      }
    });

    // Orden de categorías (más importantes primero)
    const categoryOrder = ['cPanel', 'Web Server', 'Mail', 'Security', 'Database', 'System', 'Other'];
    const sortedCategories = Object.keys(logsByCategory).sort((a, b) => {
      const aIndex = categoryOrder.indexOf(a);
      const bIndex = categoryOrder.indexOf(b);
      if (aIndex === -1 && bIndex === -1) return a.localeCompare(b);
      if (aIndex === -1) return 1;
      if (bIndex === -1) return -1;
      return aIndex - bIndex;
    });

    sortedCategories.forEach(category => {
      const categoryData = logsByCategory[category];
      const allLogs = [...categoryData.exists, ...categoryData.missing];
      
      if (allLogs.length === 0) return;

      // Crear sección de categoría
      const categorySection = document.createElement('li');
      categorySection.className = 'category-section';
      
      const categoryHeader = document.createElement('div');
      categoryHeader.className = 'category-header';
      const translatedCategory = translateCategory(category);
      const containsSelected = state.selectedId && allLogs.some(log => log.id === state.selectedId);
      const isFirstLoad = state.expandedCategories.size === 0;
      let shouldExpand = state.expandedCategories.has(category) || (containsSelected && isFirstLoad);

      categoryHeader.innerHTML = `
        <span class="category-title">${translatedCategory}</span>
        <span class="category-count">${allLogs.length}</span>
        <span class="category-toggle">${shouldExpand ? '▼' : '▶'}</span>
      `;
      
      const categoryContent = document.createElement('ul');
      categoryContent.className = 'category-content';

      // Verificar si la categoría debe estar expandida
      // Si la categoría está en el Set, está expandida
      // Si no está en el Set pero contiene el log seleccionado y es la primera carga, expandirla
      
      categoryContent.style.display = shouldExpand ? 'block' : 'none';
      
      // Renderizar logs de esta categoría
      allLogs.forEach((log) => {
        const node = elements.template.content.cloneNode(true);
        const li = node.querySelector('.log-item');
        li.dataset.id = log.id;
        li.classList.toggle('missing', !log.exists);
        li.classList.toggle('compressed', isCompressedLog(log));

        node.querySelector('.title').textContent = log.name;
        const subtitle = node.querySelector('.subtitle');
        if (!log.exists) {
          subtitle.innerHTML = `<span style="color: #94a3b8; font-size: 0.75rem;">${log.path}</span><br/><span style="color: #fca5a5;">${translate('list.not_found')}</span>`;
        } else {
          subtitle.innerHTML = buildSubtitle(log);
        }

        if (state.selectedId === log.id) {
          li.classList.add('active');
        }

        categoryContent.appendChild(node);
      });

      // Toggle para colapsar/expandir
      categoryHeader.addEventListener('click', () => {
        const isExpanded = categoryContent.style.display !== 'none';
        const newState = isExpanded ? 'none' : 'block';
        categoryContent.style.display = newState;
        const nowExpanded = newState !== 'none';
        categoryHeader.querySelector('.category-toggle').textContent = nowExpanded ? '▼' : '▶';
        if (!nowExpanded) {
          state.expandedCategories.delete(category);
        } else {
          state.expandedCategories.add(category);
        }
      });
      
      // Actualizar el ícono del toggle según el estado
      categoryHeader.querySelector('.category-toggle').textContent = 
        categoryContent.style.display !== 'none' ? '▼' : '▶';

      categorySection.appendChild(categoryHeader);
      categorySection.appendChild(categoryContent);
      fragment.appendChild(categorySection);
    });

    elements.list.appendChild(fragment);
  };

  const formatSubtitle = (log) => {
    const parts = [];
    if (typeof log.size === 'number') {
      parts.push(`${formatSize(log.size)}`);
    }
    if (log.mtime) {
      const date = new Date(log.mtime * 1000);
      parts.push(date.toLocaleString());
    }
    return parts.join(' • ');
  };

  const buildSubtitle = (log) => {
    const pathLine = `<span class="log-path">${log.path}</span>`;
    const metaParts = [];

    if (isCompressedLog(log)) {
      metaParts.push(`<span class="badge badge-compressed">${translate('badge.compressed')}</span>`);
    }

    const details = formatSubtitle(log);
    if (details) {
      metaParts.push(`<span class="meta-details">${details}</span>`);
    }

    const metaLine = metaParts.length ? `<br/>${metaParts.join(' ')}` : '';
    return `${pathLine}${metaLine}`;
  };

  const formatSize = (bytes) => {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / Math.pow(1024, exponent);
    return `${value.toFixed(value >= 100 || exponent === 0 ? 0 : 1)} ${units[exponent]}`;
  };

  const applyFilter = () => {
    const term = elements.filter.value.trim().toLowerCase();
    // Resetear "mostrar más" cuando se aplica un filtro
    if (term.length > 0) {
      state.showAllLogs = true;
    }
    if (!term) {
      state.filtered = [...state.logs];
      if (elements.filterClearBtn) {
        elements.filterClearBtn.style.display = 'none';
      }
    } else {
      state.filtered = state.logs.filter((log) =>
        [log.name, log.id].some((value) => value.toLowerCase().includes(term))
      );
    }
    renderList();
  };

  const loadLogs = async () => {
    if (state.updateInProgress) {
      console.warn('[UPDATE] Cargando logs bloqueado durante actualización');
      return;
    }
    try {
      setStatusKey('status.loading_logs');
      console.log('[DEBUG] Cargando logs desde:', baseUrl + 'mlv.cgi?api=logs&action=list');
      const json = await fetchJSON('mlv.cgi?api=logs&action=list');
      console.log('[DEBUG] Respuesta recibida:', json);
      
      if (json.status !== 'ok') {
        throw new Error(json.message || translate('status.fetch_list_failed'));
      }

      const logsData = json.data || [];
      console.log('[DEBUG] Logs encontrados:', logsData.length);
      
      if (logsData.length === 0) {
        setStatusKey('status.no_logs_configured', 'error');
        return;
      }

      // Los logs ya vienen ordenados por prioridad desde el backend
      state.logs = logsData;
      console.log('[DEBUG] Logs procesados:', state.logs.length);
      
      if (state.logs.length === 0) {
        setStatusKey('status.no_logs_configured', 'error');
        elements.list.innerHTML = `<li style="padding: 1rem; color: #fca5a5;">${translate('status.no_logs_entries')}</li>`;
        return;
      }
      
      applyFilter();
      
      // Verificar si hay logs existentes
      const existingLogs = state.logs.filter(log => log.exists);
      if (existingLogs.length === 0) {
        setStatusKey('status.warning_missing_logs', 'error');
      } else if (existingLogs.length < state.logs.length) {
        setStatusKey('status.logs_found', 'info', {
          found: existingLogs.length,
          total: state.logs.length,
        });
      } else {
        setStatus('');
      }
      
      selectFirstAvailable();
    } catch (error) {
      setStatusKey('status.error_loading_logs', 'error', { error: error.message });
      console.error('[ERROR] Error al cargar logs:', error);
      console.error('[ERROR] Stack:', error.stack);
      const errorLine = translate('status.error_loading_logs_list', { error: error.message });
      const hint = translate('notification.console_hint');
      elements.list.innerHTML = `<li style="padding: 1rem; color: #fca5a5;">${errorLine}<br/><small>${hint}</small></li>`;
    }
  };

  const selectFirstAvailable = () => {
    if (!state.selectedId && state.filtered.length > 0) {
      const candidate = state.filtered.find((log) => log.exists && !isCompressedLog(log))
        || state.filtered.find((log) => log.exists)
        || state.filtered[0];
      if (candidate) {
        selectLog(candidate.id);
      }
    }
  };

  const selectLog = (id) => {
    // Detener modo live al cambiar de log
    if (state.liveMode) {
      stopLiveMode();
    }
    
    // Encontrar la categoría del log seleccionado y expandirla si está colapsada
    const selectedLog = state.logs.find(log => log.id === id);
    if (selectedLog && selectedLog.category) {
      // Solo expandir si no estaba ya expandida (no forzar si el usuario la colapsó)
      // Pero si está colapsada, expandirla para que el usuario vea el log seleccionado
      if (!state.expandedCategories.has(selectedLog.category)) {
        state.expandedCategories.add(selectedLog.category);
      }
    }
    
    state.selectedId = id;
    state.lastLineCount = 0;
    renderList();
    loadLogContent();
  };

  const loadLogContent = async () => {
    if (!state.selectedId) {
      elements.output.textContent = translate('viewer.initial');
      return;
    }

    if (state.updateInProgress) {
      setStatusKey('status.update_in_progress_logs', 'info');
      return;
    }

    const selectedLog = state.logs.find((log) => log.id === state.selectedId);
    if (!selectedLog) {
      elements.output.textContent = translate('viewer.not_found');
      return;
    }

    if (isCompressedLog(selectedLog)) {
      showCompressedNotice(selectedLog);
      setStatusKey('status.log_compressed', 'info');
      return;
    }

    hideCompressedNotice();

    // Mostrar/ocultar botón de limpiar según si hay texto en búsqueda
    if (elements.search.value.trim()) {
      elements.clearSearchBtn.style.display = 'inline-block';
    } else {
      elements.clearSearchBtn.style.display = 'none';
    }

    const params = new URLSearchParams({
      action: 'tail',
      id: state.selectedId,
      lines: clampLines(parseInt(elements.lines.value, 10)),
      search: elements.search.value.trim(),
      case: elements.caseCheckbox.checked ? '1' : '0',
    });

    try {
      const hasSearch = elements.search.value.trim();
      if (hasSearch) {
        setStatusKey('status.searching_full');
      } else {
        setStatusKey('status.reading_log');
      }
      
      const json = await fetchJSON(`mlv.cgi?api=logs&${params.toString()}`);
      if (json.status !== 'ok') {
        throw new Error(json.message || translate('status.error_reading_log'));
      }

      const lines = json.lines || [];
      
      // En modo live, siempre recargar el contenido completo para ver cambios
      // (el servidor puede estar rotando logs o cambiando contenido)
      if (hasSearch && lines.length === 0) {
        elements.output.textContent = translate('viewer.no_matches_file');
        setStatusKey('status.search_done_zero');
      } else {
        elements.output.textContent = lines.length ? lines.join('\n') : translate('viewer.no_results');
        // Siempre hacer scroll al final para ver lo más reciente
        // Usar setTimeout para asegurar que el DOM se actualizó
        setTimeout(() => {
          elements.output.scrollTop = elements.output.scrollHeight;
        }, 0);
        // Auto-scroll al final en modo live
        if (state.liveMode && !hasSearch) {
          setStatusKey('status.live_updated', 'info', { count: lines.length });
        }
      }
      state.lastLineCount = lines.length;

      if (json.meta) {
        const subtitle = state.logs.find((log) => log.id === state.selectedId);
        if (subtitle) {
          subtitle.size = json.meta.size;
          subtitle.mtime = json.meta.mtime;
        }
        renderList();
      }

      if (!state.liveMode) {
        if (elements.search.value.trim()) {
          setStatusKey('status.search_done', 'info', { count: lines.length });
        } else {
          setStatusKey('status.showing_lines', 'info', { count: lines.length });
        }
      }
    } catch (error) {
      setStatus(error.message, 'error');
      elements.output.textContent = '';
    }
  };

  const searchAllLogs = async () => {
    if (state.updateInProgress) {
      setStatusKey('status.update_in_progress_search', 'info');
      return;
    }
    const query = elements.search.value.trim();
    if (!query) {
      setStatusKey('status.enter_text_all', 'error');
      return;
    }

    const params = new URLSearchParams({
      action: 'search_all',
      search: query,
      lines: clampLines(parseInt(elements.lines.value, 10)),
      case: elements.caseCheckbox.checked ? '1' : '0',
    });

    try {
      setStatusKey('status.searching_all');
      const json = await fetchJSON(`mlv.cgi?api=logs&${params.toString()}`);
      if (json.status !== 'ok') {
        throw new Error(json.message || translate('status.error_search_all'));
      }

      const matches = json.matches || [];
      if (!matches.length) {
        elements.output.textContent = translate('viewer.no_matches_configured');
        setStatusKey('status.global_matches_zero');
        return;
      }

      const sections = [];
      matches.forEach((entry) => {
        sections.push(`== ${entry.name} (${entry.path}) ==`);
        if (entry.matches && entry.matches.length) {
          sections.push(entry.matches.join('\n'));
        } else {
          sections.push(translate('viewer.no_matching_lines'));
        }
        sections.push('');
      });

      elements.output.textContent = sections.join('\n');

      const total = matches.reduce((sum, entry) => sum + (entry.matches ? entry.matches.length : 0), 0);
      setStatusKey('status.global_matches', 'info', { count: total });
    } catch (error) {
      setStatus(error.message, 'error');
    }
  };

  const clampLines = (value) => {
    if (!Number.isFinite(value)) return 100;
    return Math.min(Math.max(value, 10), 2000);
  };

  const handleListClick = (event) => {
    if (state.updateInProgress) {
      setStatusKey('status.update_in_progress_wait', 'info');
      return;
    }
    const item = event.target.closest('.log-item');
    if (!item || !elements.list.contains(item)) return;
    selectLog(item.dataset.id);
  };

  // Sistema de actualización y changelog
  const changelogPanel = document.getElementById('changelog-panel');
  const changelogFrame = document.getElementById('changelog-frame');
  const showChangelogBtn = document.getElementById('show-changelog-btn');
  const closeChangelogBtn = document.getElementById('close-changelog-btn');
  const updatePanel = document.getElementById('update-panel');
  const updateStatus = document.getElementById('update-status');
  const updateProgress = document.getElementById('update-progress');
  const updateMessage = document.getElementById('update-message');
  const updateBtn = document.getElementById('update-btn');
  const cancelUpdateBtn = document.getElementById('cancel-update-btn');
  const showUpdateBtn = document.getElementById('show-update-btn');

  const checkUpdate = async (showNotification = false) => {
    try {
      if (state.updateInProgress) {
        console.warn('[UPDATE] Verificación ignorada: actualización en curso');
        return { status: 'pending' };
      }
      const json = await fetchJSON('mlv.cgi?api=update&action=check');
      if (json.status === 'ok') {
        if (updateStatus) {
          const currentVersion = json.current_version || translate('update.status.unknown');
          let statusLine = translate('update.status.current', { current: currentVersion });
          if (json.remote_version) {
            statusLine += translate('update.status.available', { remote: json.remote_version });
          }
          updateStatus.textContent = statusLine;
        }
        
        // Actualizar estilo del botón si hay actualización disponible
        if (json.has_update) {
          highlightUpdateButton(json.remote_version);
          // Mostrar notificación si se solicita
          if (showNotification) {
            showUpdateNotification(json.remote_version, json.changelog);
          }
        } else {
          resetUpdateButton();
        }
        
        return json;
      }
    } catch (error) {
      console.error('Error al verificar actualización:', error);
      if (updateStatus) {
        updateStatus.textContent = translate('update.status.failed');
      }
    }
    return null;
  };
  
  const highlightUpdateButton = (newVersion) => {
    if (showUpdateBtn) {
      // Cambiar estilo del botón a llamativo
      showUpdateBtn.style.background = 'linear-gradient(135deg, rgba(34, 197, 94, 0.9), rgba(22, 163, 74, 0.9))';
      showUpdateBtn.style.border = '1px solid rgba(34, 197, 94, 0.5)';
      showUpdateBtn.style.color = 'white';
      showUpdateBtn.style.fontWeight = '600';
      showUpdateBtn.style.boxShadow = '0 4px 12px rgba(34, 197, 94, 0.4)';
      
      // Mostrar badge de notificación
      const updateBadge = document.getElementById('update-badge');
      if (updateBadge) {
        updateBadge.style.display = 'inline-block';
      }
      
      // Actualizar texto del botón
      const updateBtnText = document.getElementById('update-btn-text');
      if (updateBtnText) {
        updateBtnText.textContent = translate('button.update_highlight', { version: newVersion });
      }
    }
  };
  
  const resetUpdateButton = () => {
    if (showUpdateBtn) {
      // Restaurar estilo original
      showUpdateBtn.style.background = 'rgba(148, 163, 184, 0.2)';
      showUpdateBtn.style.border = '1px solid rgba(148, 163, 184, 0.3)';
      showUpdateBtn.style.color = '#e2e8f0';
      showUpdateBtn.style.fontWeight = 'normal';
      showUpdateBtn.style.boxShadow = 'none';
      
      // Ocultar badge
      const updateBadge = document.getElementById('update-badge');
      if (updateBadge) {
        updateBadge.style.display = 'none';
      }
      
      // Restaurar texto original
      const updateBtnText = document.getElementById('update-btn-text');
      if (updateBtnText) {
        updateBtnText.textContent = translate('button.update');
      }
    }
  };
  
  const showUpdateNotification = (newVersion, changelog) => {
    // Crear o actualizar notificación
    let notification = document.getElementById('update-notification');
    if (!notification) {
      notification = document.createElement('div');
      notification.id = 'update-notification';
      notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.95), rgba(22, 163, 74, 0.95));
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 0.75rem;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        z-index: 1001;
        max-width: 400px;
        cursor: pointer;
        transition: transform 0.2s ease;
      `;
      document.body.appendChild(notification);
    }
    
    let changelogText = '';
    if (changelog) {
      // Escapar HTML para prevenir XSS y manejar caracteres especiales correctamente
      const escapedChangelog = changelog
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/\n/g, '<br>');
      changelogText = `<div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid rgba(255, 255, 255, 0.2); font-size: 0.85rem; max-height: 200px; overflow-y: auto;">${escapedChangelog}</div>`;
    }
    
    const notifTitle = translate('update.notification.title', { version: newVersion });
    const notifSubtitle = translate('update.notification.subtitle');
    notification.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: start; gap: 1rem;">
        <div style="flex: 1;">
          <div style="font-weight: 600; margin-bottom: 0.25rem;">${notifTitle}</div>
          <div style="font-size: 0.85rem; opacity: 0.9;">${notifSubtitle}</div>
          ${changelogText}
        </div>
        <button id="close-update-notification" style="background: rgba(255, 255, 255, 0.2); border: none; color: white; width: 24px; height: 24px; border-radius: 50%; cursor: pointer; font-size: 1rem; line-height: 1; padding: 0;">✕</button>
      </div>
    `;
    
    // Cerrar notificación
    const closeBtn = notification.querySelector('#close-update-notification');
    if (closeBtn) {
      closeBtn.setAttribute('title', translate('button.close'));
    }
    
    // Abrir panel de actualización al hacer clic
    notification.addEventListener('click', (e) => {
      if (e.target !== closeBtn && !closeBtn.contains(e.target)) {
        showUpdatePanel();
        notification.remove();
      }
    });
    
    // Auto-ocultar después de 10 segundos
    setTimeout(() => {
      if (notification && notification.parentNode) {
        notification.style.opacity = '0';
        notification.style.transition = 'opacity 0.3s ease';
        setTimeout(() => notification.remove(), 300);
      }
    }, 10000);
  };

  const showChangelogPanel = () => {
    if (!changelogPanel) {
      console.error('[CHANGELOG] changelogPanel no encontrado');
      return;
    }

    changelogPanel.style.display = 'flex';
    changelogPanel.style.visibility = 'visible';
    changelogPanel.style.opacity = '1';
    changelogPanel.style.zIndex = '10000';
    changelogPanel.style.position = 'fixed';

    if (changelogFrame) {
      const targetUrl = window.MLV_CHANGELOG_URL || 'https://dev.denialhost.com/cpanel-multi-log-viewer-version.txt';
      const noCacheUrl = `${targetUrl}?ts=${Date.now()}`;
      changelogFrame.src = noCacheUrl;
    }
  };

  const showUpdatePanel = async () => {
    if (updatePanel) {
      updatePanel.style.display = 'flex';
      await checkUpdate();
    }
  };

  const performUpdate = async () => {
    if (state.updateInProgress) {
      console.warn('[UPDATE] Solicitud ignorada: actualización en curso');
      return;
    }
    state.updateInProgress = true;
    updateProgress.style.display = 'block';
    updateBtn.disabled = true;
    updateMessage.textContent = translate('update.progress.downloading');
    
    try {
      const json = await fetchJSON('mlv.cgi?api=update&action=update');
      if (json.status === 'ok') {
        updateMessage.textContent = translate('update.progress.done');
        if (json.output) {
          console.log('[UPDATE] Salida de instalación:', json.output);
        }
        setTimeout(() => {
          // Forzar recarga completa sin caché
          window.location.href = window.location.href.split('?')[0] + '?nocache=' + Date.now();
        }, 2000);
      } else {
        const errorMsg = json.message || translate('update.error.unknown');
        const messageLines = [`${translate('update.error.prefix')} ${errorMsg}`];

        if (json.detail) {
          messageLines.push(`${translate('update.error.details')}\n${json.detail}`);
        }

        if (json.debug) {
          messageLines.push(`${translate('update.error.debug')}\n${json.debug}`);
        }

        if (json.exit_code !== undefined) {
          messageLines.push(translate('update.error.exit_code', { code: json.exit_code }));
        }

        // Mostrar el error completo en el mensaje
        updateMessage.textContent = messageLines.join('\n\n');
        updateMessage.style.whiteSpace = 'pre-wrap'; // Permitir saltos de línea
        updateMessage.style.maxHeight = '400px';
        updateMessage.style.overflow = 'auto';
        
        console.error('[UPDATE] Error completo:', json);
        updateBtn.disabled = false;
      }
    } catch (error) {
      updateMessage.textContent = `${translate('update.error.prefix')} ${error.message}`;
      console.error('[UPDATE] Excepción:', error);
      updateBtn.disabled = false;
    }
    state.updateInProgress = false;
  };

  const startLiveMode = () => {
    if (state.liveMode) return;
    
    if (state.updateInProgress) {
      setStatusKey('status.update_in_progress_live', 'error');
      return;
    }

    if (!state.selectedId) {
      setStatusKey('status.select_log_live', 'error');
      return;
    }

    const selectedLog = state.logs.find((log) => log.id === state.selectedId);
    if (isCompressedLog(selectedLog)) {
      setStatusKey('status.live_not_available_compressed', 'error');
      return;
    }

    // No permitir modo live con búsqueda activa
    if (elements.search.value.trim()) {
      setStatusKey('status.live_not_available_search', 'error');
      return;
    }
    
    state.liveMode = true;
    state.lastLineCount = 0;
    elements.liveBtn.style.display = 'none';
    elements.pauseBtn.style.display = 'inline-block';
    elements.pauseBtn.classList.add('live-active');
    elements.pauseBtn.style.background = 'linear-gradient(135deg, rgba(34, 197, 94, 0.85), rgba(22, 163, 74, 0.9))';
    elements.pauseBtn.style.color = 'white';
    elements.pauseBtn.title = translate('tooltip.pause_live');
    elements.refreshBtn.disabled = true;
    elements.search.disabled = true;
    
    // Cargar contenido inicial
    loadLogContent();
    
    // Iniciar auto-refresh cada 5 segundos
    state.liveInterval = setInterval(() => {
      if (state.liveMode && state.selectedId && !elements.search.value.trim()) {
        loadLogContent();
      }
    }, 5000);
    
    setStatusKey('status.live_started', 'info');
  };
  
  const stopLiveMode = () => {
    if (!state.liveMode) return;
    
    state.liveMode = false;
    elements.liveBtn.style.display = 'inline-block';
    elements.pauseBtn.style.display = 'none';
    elements.pauseBtn.classList.remove('live-active');
    elements.pauseBtn.style.background = '';
    elements.pauseBtn.style.color = '';
    elements.refreshBtn.disabled = false;
    elements.search.disabled = false;
    
    if (state.liveInterval) {
      clearInterval(state.liveInterval);
      state.liveInterval = null;
    }
    
    setStatusKey('status.live_paused');
  };

  const bindEvents = () => {
    elements.list.addEventListener('click', handleListClick);
    elements.filter.addEventListener('input', () => {
      applyFilter();
      if (elements.filterClearBtn) {
        elements.filterClearBtn.style.display = elements.filter.value.trim() ? 'flex' : 'none';
      }
    });
    if (elements.filterClearBtn) {
      elements.filterClearBtn.addEventListener('click', () => {
        elements.filter.value = '';
        elements.filterClearBtn.style.display = 'none';
        applyFilter();
      });
    }
    elements.refreshBtn.addEventListener('click', () => {
      if (state.updateInProgress) {
        setStatusKey('status.update_in_progress_wait', 'info');
        return;
      }
      stopLiveMode();
      loadLogContent();
    });
    elements.liveBtn.addEventListener('click', startLiveMode);
    elements.pauseBtn.addEventListener('click', stopLiveMode);
    elements.searchAllBtn.addEventListener('click', searchAllLogs);
    elements.lines.addEventListener('change', () => {
      elements.lines.value = clampLines(parseInt(elements.lines.value, 10));
    });
    elements.search.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        stopLiveMode(); // Detener modo live al buscar
        loadLogContent();
      }
    });
    
    // Detener modo live si se cambia el campo de búsqueda
    elements.search.addEventListener('input', () => {
      // Mostrar/ocultar botón de limpiar según si hay texto
      if (elements.search.value.trim()) {
        elements.clearSearchBtn.style.display = 'inline-block';
      } else {
        elements.clearSearchBtn.style.display = 'none';
      }
      
      if (state.liveMode && elements.search.value.trim()) {
        stopLiveMode();
      }
    });
    
    // Botón para limpiar búsqueda
    if (elements.clearSearchBtn) {
      elements.clearSearchBtn.addEventListener('click', () => {
        if (state.updateInProgress) {
          setStatusKey('status.update_in_progress_wait', 'info');
          return;
        }
        elements.search.value = '';
        elements.clearSearchBtn.style.display = 'none';
        stopLiveMode();
        loadLogContent();
      });
    }
    
    
    // Eventos de actualización
    if (showChangelogBtn) {
      console.log('[CHANGELOG] Botón encontrado, agregando event listener');
      showChangelogBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        console.log('[CHANGELOG] Botón clickeado');
        showChangelogPanel();
      });
    } else {
      console.error('[CHANGELOG] Botón showChangelogBtn no encontrado');
    }
    if (closeChangelogBtn && changelogPanel) {
      closeChangelogBtn.addEventListener('click', () => {
        changelogPanel.style.display = 'none';
        changelogPanel.style.visibility = 'hidden';
        changelogPanel.style.opacity = '0';
      });
    }
    // Cerrar changelog al hacer clic fuera del panel
    if (changelogPanel) {
      changelogPanel.addEventListener('click', (e) => {
        if (e.target === changelogPanel) {
          changelogPanel.style.display = 'none';
        }
      });
    }
    if (showUpdateBtn) {
      showUpdateBtn.addEventListener('click', showUpdatePanel);
    }
    if (updateBtn) {
      updateBtn.addEventListener('click', performUpdate);
    }
    if (cancelUpdateBtn) {
      cancelUpdateBtn.addEventListener('click', () => {
        if (updatePanel) {
          updatePanel.style.display = 'none';
        }
      });
    }

    if (elements.downloadCompressedBtn) {
      elements.downloadCompressedBtn.addEventListener('click', (event) => {
        event.preventDefault();
        const targetId = elements.downloadCompressedBtn.dataset.logId || state.selectedId;
        if (!targetId) return;
        const log = state.logs.find((item) => item.id === targetId);
        if (!isCompressedLog(log)) return;
        const url = `mlv.cgi?download=${encodeURIComponent(targetId)}`;
        window.open(url, '_blank', 'noopener');
      });
    }
  };

  const init = () => {
    bindEvents();
    loadLogs();
    // Verificar actualizaciones al cargar (con notificación si hay)
    checkUpdate(true);
    
    // Verificar actualizaciones periódicamente
    // Usar intervalo configurado o 30 minutos por defecto
    const updateInterval = window.MLV_UPDATE_CHECK_INTERVAL || (30 * 60 * 1000);
    setInterval(async () => {
      const updateInfo = await checkUpdate(false);
      // Si hay actualización y no hay notificación visible, mostrarla
      if (updateInfo && updateInfo.has_update) {
        const existingNotification = document.getElementById('update-notification');
        if (!existingNotification) {
          showUpdateNotification(updateInfo.remote_version, updateInfo.changelog);
        }
      }
    }, updateInterval);
  };

  document.addEventListener('DOMContentLoaded', init);
})();

