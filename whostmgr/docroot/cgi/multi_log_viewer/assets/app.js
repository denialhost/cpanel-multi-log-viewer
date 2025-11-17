(() => {
  const state = {
    logs: [],
    filtered: [],
    selectedId: null,
    liveMode: false,
    liveInterval: null,
    lastLineCount: 0,
    showAllLogs: false,
  };

  const elements = {
    list: document.getElementById('logs'),
    filter: document.getElementById('filter-input'),
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
  };

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
      // Si la URL no es absoluta, construirla desde la base
      const fullUrl = url.startsWith('http') ? url : baseUrl + url;
      const response = await fetch(fullUrl, { 
        credentials: 'same-origin',
        headers: {
          'Accept': 'application/json',
        }
      });
      if (!response.ok) {
        const errorText = await response.text();
        let errorData;
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { message: errorText || `HTTP ${response.status}` };
        }
        throw new Error(errorData.message || errorData.detail || `HTTP ${response.status}`);
      }
      return await response.json();
    } catch (error) {
      console.error('Error en fetchJSON:', error, 'URL:', url);
      throw error;
    }
  };

  const setStatus = (message, type = 'info') => {
    elements.status.textContent = message || '';
    elements.status.className = type;
  };

  const renderList = () => {
    elements.list.innerHTML = '';
    const fragment = document.createDocumentFragment();

    const SHOW_MORE_THRESHOLD = 15;
    const hasFilter = elements.filter.value.trim().length > 0;
    const existingLogs = state.filtered.filter(log => log.exists);
    const missingLogs = state.filtered.filter(log => !log.exists);
    
    // Mostrar logs existentes primero
    const logsToShow = hasFilter 
      ? state.filtered  // Si hay filtro, mostrar todos
      : existingLogs.slice(0, SHOW_MORE_THRESHOLD);  // Sin filtro, solo primeros 15
    
    const remainingLogs = hasFilter 
      ? [] 
      : existingLogs.slice(SHOW_MORE_THRESHOLD).concat(missingLogs);

    logsToShow.forEach((log) => {
      const node = elements.template.content.cloneNode(true);
      const li = node.querySelector('.log-item');
      li.dataset.id = log.id;
      li.classList.toggle('missing', !log.exists);

      node.querySelector('.title').textContent = log.name;
      const subtitle = node.querySelector('.subtitle');
      if (!log.exists) {
        subtitle.innerHTML = `<span style="color: #94a3b8; font-size: 0.75rem;">${log.path}</span><br/><span style="color: #fca5a5;">No encontrado</span>`;
      } else {
        subtitle.innerHTML = `<span style="color: #94a3b8; font-size: 0.75rem;">${log.path}</span><br/><span>${formatSubtitle(log)}</span>`;
      }

      if (state.selectedId === log.id) {
        li.classList.add('active');
      }

      fragment.appendChild(node);
    });

    elements.list.appendChild(fragment);

    // Agregar botón "mostrar más" si hay logs restantes
    if (remainingLogs.length > 0 && !state.showAllLogs) {
      const showMoreBtn = document.createElement('li');
      showMoreBtn.className = 'show-more-item';
      showMoreBtn.innerHTML = `
        <button class="show-more-btn" style="width: 100%; padding: 0.75rem; background: rgba(148, 163, 184, 0.1); border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 0.5rem; color: #cbd5e1; cursor: pointer; font-size: 0.9rem;">
          Mostrar más (${remainingLogs.length} logs adicionales)
        </button>
      `;
      showMoreBtn.querySelector('button').addEventListener('click', () => {
        state.showAllLogs = true;
        renderList();
      });
      elements.list.appendChild(showMoreBtn);
    } else if (remainingLogs.length > 0 && state.showAllLogs) {
      // Mostrar logs restantes
      remainingLogs.forEach((log) => {
        const node = elements.template.content.cloneNode(true);
        const li = node.querySelector('.log-item');
        li.dataset.id = log.id;
        li.classList.toggle('missing', !log.exists);

        node.querySelector('.title').textContent = log.name;
        const subtitle = node.querySelector('.subtitle');
        if (!log.exists) {
          subtitle.innerHTML = `<span style="color: #94a3b8; font-size: 0.75rem;">${log.path}</span><br/><span style="color: #fca5a5;">No encontrado</span>`;
        } else {
          subtitle.innerHTML = `<span style="color: #94a3b8; font-size: 0.75rem;">${log.path}</span><br/><span>${formatSubtitle(log)}</span>`;
        }

        if (state.selectedId === log.id) {
          li.classList.add('active');
        }

        fragment.appendChild(node);
      });
      elements.list.appendChild(fragment);
    }
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
    } else {
      state.filtered = state.logs.filter((log) =>
        [log.name, log.id].some((value) => value.toLowerCase().includes(term))
      );
    }
    renderList();
  };

  const loadLogs = async () => {
    try {
      setStatus('Cargando listado de logs…');
      console.log('[DEBUG] Cargando logs desde:', baseUrl + 'mlv.cgi?api=logs&action=list');
      const json = await fetchJSON('mlv.cgi?api=logs&action=list');
      console.log('[DEBUG] Respuesta recibida:', json);
      
      if (json.status !== 'ok') {
        throw new Error(json.message || 'No se pudo obtener la lista de logs');
      }

      const logsData = json.data || [];
      console.log('[DEBUG] Logs encontrados:', logsData.length);
      
      if (logsData.length === 0) {
        setStatus('No se encontraron logs configurados. Verifique log_sources.json', 'error');
        return;
      }

      // Los logs ya vienen ordenados por prioridad desde el backend
      state.logs = logsData;
      console.log('[DEBUG] Logs procesados:', state.logs.length);
      
      if (state.logs.length === 0) {
        setStatus('No se encontraron logs configurados. Verifique log_sources.json', 'error');
        elements.list.innerHTML = '<li style="padding: 1rem; color: #fca5a5;">No hay logs configurados</li>';
        return;
      }
      
      applyFilter();
      
      // Verificar si hay logs existentes
      const existingLogs = state.logs.filter(log => log.exists);
      if (existingLogs.length === 0) {
        setStatus('Advertencia: Ninguno de los logs configurados existe en el servidor', 'error');
      } else if (existingLogs.length < state.logs.length) {
        setStatus(`Se encontraron ${existingLogs.length} de ${state.logs.length} logs disponibles`, 'info');
      } else {
        setStatus('');
      }
      
      selectFirstAvailable();
    } catch (error) {
      setStatus('Error al cargar logs: ' + error.message, 'error');
      console.error('[ERROR] Error al cargar logs:', error);
      console.error('[ERROR] Stack:', error.stack);
      elements.list.innerHTML = `<li style="padding: 1rem; color: #fca5a5;">Error: ${error.message}<br/><small>Revisa la consola del navegador (F12) para más detalles</small></li>`;
    }
  };

  const selectFirstAvailable = () => {
    if (!state.selectedId && state.filtered.length > 0) {
      const candidate = state.filtered.find((log) => log.exists) || state.filtered[0];
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
    state.selectedId = id;
    state.lastLineCount = 0;
    renderList();
    loadLogContent();
  };

  const loadLogContent = async () => {
    if (!state.selectedId) {
      elements.output.textContent = 'Seleccione un log para comenzar.';
      return;
    }
    
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
        setStatus('Buscando en el archivo completo…');
      } else {
        setStatus('Leyendo log…');
      }
      
      const json = await fetchJSON(`mlv.cgi?api=logs&${params.toString()}`);
      if (json.status !== 'ok') {
        throw new Error(json.message || 'Error al leer el log');
      }

      const lines = json.lines || [];
      
      // En modo live, siempre recargar el contenido completo para ver cambios
      // (el servidor puede estar rotando logs o cambiando contenido)
      if (hasSearch && lines.length === 0) {
        elements.output.textContent = '(No se encontraron coincidencias en el archivo)';
        setStatus('Búsqueda completada: 0 coincidencias');
      } else {
        elements.output.textContent = lines.length ? lines.join('\n') : '(Sin resultados)';
        // Auto-scroll al final en modo live
        if (state.liveMode && !hasSearch) {
          elements.output.scrollTop = elements.output.scrollHeight;
          setStatus(`Live: ${lines.length} líneas - actualizado`);
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
          setStatus(`Búsqueda: ${lines.length} coincidencia(s) encontrada(s)`);
        } else {
          setStatus(`Mostrando ${lines.length} línea(s)`);
        }
      }
    } catch (error) {
      setStatus(error.message, 'error');
      elements.output.textContent = '';
    }
  };

  const searchAllLogs = async () => {
    const query = elements.search.value.trim();
    if (!query) {
      setStatus('Introduce un texto para buscar en todos los logs', 'error');
      return;
    }

    const params = new URLSearchParams({
      action: 'search_all',
      search: query,
      lines: clampLines(parseInt(elements.lines.value, 10)),
      case: elements.caseCheckbox.checked ? '1' : '0',
    });

    try {
      setStatus('Buscando coincidencias en todos los logs…');
      const json = await fetchJSON(`mlv.cgi?api=logs&${params.toString()}`);
      if (json.status !== 'ok') {
        throw new Error(json.message || 'Error al realizar la búsqueda global');
      }

      const matches = json.matches || [];
      if (!matches.length) {
        elements.output.textContent = '(Sin coincidencias en los logs configurados)';
        setStatus('Búsqueda global: 0 coincidencias');
        return;
      }

      const sections = [];
      matches.forEach((entry) => {
        sections.push(`== ${entry.name} (${entry.path}) ==`);
        if (entry.matches && entry.matches.length) {
          sections.push(entry.matches.join('\n'));
        } else {
          sections.push('(Sin líneas coincidentes disponibles)');
        }
        sections.push('');
      });

      elements.output.textContent = sections.join('\n');

      const total = matches.reduce((sum, entry) => sum + (entry.matches ? entry.matches.length : 0), 0);
      setStatus(`Búsqueda global: ${total} coincidencia(s)`);
    } catch (error) {
      setStatus(error.message, 'error');
    }
  };

  const clampLines = (value) => {
    if (!Number.isFinite(value)) return 200;
    return Math.min(Math.max(value, 10), 2000);
  };

  const handleListClick = (event) => {
    const item = event.target.closest('.log-item');
    if (!item || !elements.list.contains(item)) return;
    selectLog(item.dataset.id);
  };

  // Sistema de actualización
  const updatePanel = document.getElementById('update-panel');
  const updateStatus = document.getElementById('update-status');
  const updateProgress = document.getElementById('update-progress');
  const updateMessage = document.getElementById('update-message');
  const updateBtn = document.getElementById('update-btn');
  const cancelUpdateBtn = document.getElementById('cancel-update-btn');
  const showUpdateBtn = document.getElementById('show-update-btn');

  const checkUpdate = async () => {
    try {
      const json = await fetchJSON('mlv.cgi?api=update&action=check');
      if (json.status === 'ok') {
        updateStatus.textContent = `Versión actual: ${json.current_version || 'Desconocida'}`;
      }
    } catch (error) {
      console.error('Error al verificar actualización:', error);
      if (updateStatus) {
        updateStatus.textContent = 'No se pudo verificar la versión';
      }
    }
  };

  const showUpdatePanel = async () => {
    if (updatePanel) {
      updatePanel.style.display = 'flex';
      await checkUpdate();
    }
  };

  const performUpdate = async () => {
    updateProgress.style.display = 'block';
    updateBtn.disabled = true;
    updateMessage.textContent = 'Descargando actualización...';
    
    try {
      const json = await fetchJSON('mlv.cgi?api=update&action=update');
      if (json.status === 'ok') {
        updateMessage.textContent = '✓ Actualización completada. Recargando página...';
        if (json.output) {
          console.log('[UPDATE] Salida de instalación:', json.output);
        }
        setTimeout(() => {
          window.location.reload();
        }, 2000);
      } else {
        const errorMsg = json.message || 'Error desconocido';
        let errorDetail = '';
        
        if (json.detail) {
          errorDetail = `\n\nDetalles:\n${json.detail}`;
        }
        
        if (json.debug) {
          errorDetail += `\n\nDebug:\n${json.debug}`;
        }
        
        if (json.exit_code !== undefined) {
          errorDetail += `\n\nCódigo de salida: ${json.exit_code}`;
        }
        
        // Mostrar el error completo en el mensaje
        updateMessage.textContent = `✗ Error: ${errorMsg}${errorDetail}`;
        updateMessage.style.whiteSpace = 'pre-wrap'; // Permitir saltos de línea
        updateMessage.style.maxHeight = '400px';
        updateMessage.style.overflow = 'auto';
        
        console.error('[UPDATE] Error completo:', json);
        updateBtn.disabled = false;
      }
    } catch (error) {
      updateMessage.textContent = `✗ Error: ${error.message}`;
      console.error('[UPDATE] Excepción:', error);
      updateBtn.disabled = false;
    }
  };

  const startLiveMode = () => {
    if (state.liveMode) return;
    
    if (!state.selectedId) {
      setStatus('Seleccione un log para activar el modo live', 'error');
      return;
    }
    
    // No permitir modo live con búsqueda activa
    if (elements.search.value.trim()) {
      setStatus('El modo live no está disponible cuando hay una búsqueda activa', 'error');
      return;
    }
    
    state.liveMode = true;
    state.lastLineCount = 0;
    elements.liveBtn.style.display = 'none';
    elements.pauseBtn.style.display = 'inline-block';
    elements.pauseBtn.classList.add('live-active');
    elements.pauseBtn.style.background = 'linear-gradient(135deg, rgba(34, 197, 94, 0.85), rgba(22, 163, 74, 0.9))';
    elements.pauseBtn.style.color = 'white';
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
    
    setStatus('Modo live activado - actualizando cada 5 segundos', 'info');
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
    
    setStatus('Modo live pausado');
  };

  const bindEvents = () => {
    elements.list.addEventListener('click', handleListClick);
    elements.filter.addEventListener('input', () => {
      applyFilter();
    });
    elements.refreshBtn.addEventListener('click', () => {
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
    elements.clearSearchBtn.addEventListener('click', () => {
      elements.search.value = '';
      elements.clearSearchBtn.style.display = 'none';
      stopLiveMode();
      loadLogContent();
    });
    
    // Eventos de actualización
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
  };

  const init = () => {
    bindEvents();
    loadLogs();
  };

  document.addEventListener('DOMContentLoaded', init);
})();

