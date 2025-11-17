#!/bin/bash

# Guardar el directorio de trabajo original
ORIGINAL_PWD="$(pwd)"

set -euo pipefail

# Forzar locale neutro para evitar caracteres tipográficos (ej. comillas UTF-8) en salidas de comandos cPanel
export LC_ALL=C
export LANG=C

PLUGIN_NAME="mlv"
PLUGIN_VERSION="1.1.3"
BASE_DIR="/usr/local/cpanel/whostmgr/docroot/cgi/${PLUGIN_NAME}"
APP_CONFIG_DST="/var/cpanel/apps/${PLUGIN_NAME}.conf"

# Detectar el directorio desde donde se ejecuta el script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_DIR="$(pwd)"
SOURCE_DIR="${SCRIPT_DIR}"

# Verificar que estamos en el directorio correcto (debe tener whostmgr/docroot/cgi/...)
# Verificar múltiples condiciones posibles
if [[ -d "${SOURCE_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}" ]]; then
    # Estamos en el directorio raíz del paquete, correcto
    echo "[INFO] Ejecutando desde directorio fuente: ${SOURCE_DIR}";
elif [[ -d "${SOURCE_DIR}/appconfig" ]] && [[ -f "${SOURCE_DIR}/install.sh" ]]; then
    # También correcto si estamos en el directorio raíz
    echo "[INFO] Ejecutando desde directorio fuente: ${SOURCE_DIR}";
elif [[ -f "${SOURCE_DIR}/install.sh" ]] && [[ -d "${SOURCE_DIR}/whostmgr" ]]; then
    # También correcto si estamos en el directorio raíz
    echo "[INFO] Ejecutando desde directorio fuente: ${SOURCE_DIR}";
elif [[ -f "${CURRENT_DIR}/install.sh" ]] && [[ -d "${CURRENT_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}" ]]; then
    # Los archivos están en el directorio actual (tar.gz mal empaquetado)
    SOURCE_DIR="${CURRENT_DIR}"
    echo "[WARN] Los archivos están en el directorio actual (${SOURCE_DIR})" >&2;
    echo "[WARN] El tar.gz debería crear un subdirectorio 'cpanel-multi-log-viewer', pero continuando..." >&2;
    echo "[INFO] Usando directorio actual como fuente: ${SOURCE_DIR}";
elif [[ -f "install.sh" ]] && [[ -d "whostmgr/docroot/cgi/${PLUGIN_NAME}" ]]; then
    # Los archivos están en el directorio actual (tar.gz mal empaquetado)
    SOURCE_DIR="$(pwd)"
    echo "[WARN] Los archivos están en el directorio actual (${SOURCE_DIR})" >&2;
    echo "[WARN] El tar.gz debería crear un subdirectorio 'cpanel-multi-log-viewer', pero continuando..." >&2;
    echo "[INFO] Usando directorio actual como fuente: ${SOURCE_DIR}";
else
    echo "[ERROR] Este script debe ejecutarse desde el directorio raíz del paquete del plugin" >&2;
    echo "[ERROR] SCRIPT_DIR: ${SCRIPT_DIR}" >&2;
    echo "[ERROR] CURRENT_DIR: ${CURRENT_DIR}" >&2;
    echo "[ERROR] Contenido de SCRIPT_DIR:" >&2;
    ls -la "${SCRIPT_DIR}" | head -10 >&2;
    echo "[ERROR] Contenido de CURRENT_DIR:" >&2;
    ls -la "${CURRENT_DIR}" | head -10 >&2;
    echo "[ERROR] Debe contener: whostmgr/docroot/cgi/${PLUGIN_NAME}/ y appconfig/" >&2;
    exit 1;
fi

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    echo "[ERROR] Debe ejecutar este script como root." >&2
    exit 1
  fi
}

copy_files() {
  echo "[INFO] Copiando archivos del plugin...";
  echo "[DEBUG] SOURCE_DIR: ${SOURCE_DIR}";
  echo "[DEBUG] Directorio de trabajo actual: $(pwd)";
  
  # Crear estructura EXACTAMENTE como CSF: script principal en subdirectorio /cgi/multi_log_viewer/
  BASE_CGI_DIR="/usr/local/cpanel/whostmgr/docroot/cgi"
  PLUGIN_DIR="${BASE_CGI_DIR}/${PLUGIN_NAME}"
  
  echo "[DEBUG] PLUGIN_DIR (destino): ${PLUGIN_DIR}";
  
  # Crear directorio del plugin (como configserver para CSF)
  install -d "${PLUGIN_DIR}/assets" "${PLUGIN_DIR}/config" "${PLUGIN_DIR}/lib"
  chmod 700 "${PLUGIN_DIR}" 2>/dev/null || true

  # Instalar script principal en el subdirectorio (como CSF: /cgi/configserver/csf.cgi)
  local MLV_SRC="${SOURCE_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}/mlv.cgi"
  echo "[DEBUG] Buscando mlv.cgi en: ${MLV_SRC}";
  
  if [[ ! -f "${MLV_SRC}" ]]; then
    echo "[ERROR] No se encontró mlv.cgi en el paquete: ${MLV_SRC}" >&2
    echo "[DEBUG] Listando contenido de ${SOURCE_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}/:" >&2
    ls -la "${SOURCE_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}/" 2>&1 || true
    exit 1
  fi
  
  echo "[OK] mlv.cgi encontrado en: ${MLV_SRC}";
  
  # Función para convertir line endings y copiar archivo
  copy_and_fix_cgi() {
    local src="$1"
    local dst="$2"
    
    if [[ ! -f "${src}" ]]; then
      echo "[ERROR] Archivo fuente no existe: ${src}" >&2
      return 1
    fi
    
    echo "[INFO] Procesando $(basename ${src})..."
    
    # Método 1: Intentar con tr (más confiable para eliminar \r)
    if command -v tr >/dev/null 2>&1; then
      if tr -d '\r' < "${src}" > "${dst}.tmp" 2>/dev/null; then
        if [[ -s "${dst}.tmp" ]]; then
          mv "${dst}.tmp" "${dst}"
          chmod 700 "${dst}"
          echo "[OK] $(basename ${dst}) copiado con tr"
          return 0
        fi
      fi
    fi
    
    # Método 2: Intentar con perl
    if command -v perl >/dev/null 2>&1; then
      if perl -pe 's/\r\n?/\n/g' < "${src}" > "${dst}.tmp" 2>/dev/null; then
        if [[ -s "${dst}.tmp" ]]; then
          mv "${dst}.tmp" "${dst}"
          chmod 700 "${dst}"
          echo "[OK] $(basename ${dst}) copiado con perl"
          return 0
        fi
      fi
    fi
    
    # Método 3: Intentar con sed
    if sed 's/\r$//' "${src}" > "${dst}.tmp" 2>/dev/null; then
      if [[ -s "${dst}.tmp" ]]; then
        mv "${dst}.tmp" "${dst}"
        chmod 700 "${dst}"
        echo "[OK] $(basename ${dst}) copiado con sed"
        return 0
      fi
    fi
    
    # Método 4: Copiar directamente y luego convertir con múltiples métodos
    cp "${src}" "${dst}" 2>/dev/null || {
      echo "[ERROR] No se pudo copiar ${src} a ${dst}" >&2
      return 1
    }
    
    # Forzar conversión con múltiples métodos en secuencia
    # Método 4a: tr (más confiable)
    if command -v tr >/dev/null 2>&1; then
      tr -d '\r' < "${dst}" > "${dst}.tmp2" 2>/dev/null && mv "${dst}.tmp2" "${dst}"
    fi
    
    # Método 4b: dos2unix
    if command -v dos2unix >/dev/null 2>&1; then
      dos2unix "${dst}" 2>/dev/null || true
    fi
    
    # Método 4c: sed in-place
    sed -i 's/\r$//' "${dst}" 2>/dev/null || sed -i '' 's/\r$//' "${dst}" 2>/dev/null || true
    
    # Método 4d: perl in-place
    perl -pi -e 's/\r\n?/\n/g' "${dst}" 2>/dev/null || true
    
    # Verificación final: si todavía tiene CRLF, forzar con tr de nuevo
    if command -v file >/dev/null 2>&1 && command -v tr >/dev/null 2>&1; then
      if file "${dst}" 2>/dev/null | grep -q "CRLF"; then
        echo "[WARN] Forzando conversión adicional con tr..."
        tr -d '\r' < "${dst}" > "${dst}.final" 2>/dev/null && mv "${dst}.final" "${dst}"
      fi
    fi
    
    chmod 700 "${dst}"
    echo "[OK] $(basename ${dst}) copiado y convertido"
    return 0
  }
  
  # Copiar mlv.cgi como mlv.cgi en el subdirectorio (igual que CSF)
  echo "[INFO] Copiando script principal..."
  copy_and_fix_cgi "${MLV_SRC}" "${PLUGIN_DIR}/mlv.cgi"
  
  # Verificar que el archivo principal existe y es ejecutable
  if [[ ! -f "${PLUGIN_DIR}/${PLUGIN_NAME}.cgi" ]]; then
    echo "[ERROR] ${PLUGIN_NAME}.cgi no existe después de la instalación" >&2
    exit 1
  fi
  
  if [[ ! -x "${PLUGIN_DIR}/${PLUGIN_NAME}.cgi" ]]; then
    echo "[ERROR] ${PLUGIN_NAME}.cgi no es ejecutable después de la instalación" >&2
    chmod 700 "${PLUGIN_DIR}/${PLUGIN_NAME}.cgi"
  fi
  
  # Verificación adicional: asegurar que el shebang y WHMADDON están presentes
  echo "[INFO] Verificando integridad de los scripts CGI..."
  
  for script in "${PLUGIN_DIR}/mlv.cgi"; do
    if [[ ! -f "${script}" ]]; then
      continue
    fi
    
    script_name=$(basename "${script}")
    echo "[INFO] Verificando ${script_name}..."
    
    # FORZAR conversión de line endings una vez más (por si acaso)
    if command -v tr >/dev/null 2>&1; then
      tr -d '\r' < "${script}" > "${script}.verify" 2>/dev/null && mv "${script}.verify" "${script}"
    fi
    
    # Verificar shebang
    first_line=$(head -1 "${script}" 2>/dev/null | tr -d '\r\n')
    if [[ "${first_line}" =~ ^#!/usr/local/cpanel/3rdparty/bin/perl ]]; then
      echo "  ✓ Shebang correcto"
    else
      echo "  ✗ ADVERTENCIA: Shebang incorrecto en ${script_name}"
      echo "    Primera línea: '${first_line}'"
      echo "    Bytes: $(head -1 "${script}" 2>/dev/null | od -c | head -1)"
    fi
    
    # Verificar WHMADDON (debe estar en la línea 2)
    second_line=$(sed -n '2p' "${script}" 2>/dev/null | tr -d '\r\n')
    if [[ "${second_line}" =~ ^#WHMADDON ]]; then
      echo "  ✓ Comentario #WHMADDON presente"
    else
      echo "  ✗ ADVERTENCIA: No se encontró #WHMADDON en línea 2 de ${script_name}"
      echo "    Segunda línea: '${second_line}'"
    fi
    
    # Verificar que no tenga CRLF
    if command -v file >/dev/null 2>&1; then
      file_output=$(file "${script}" 2>/dev/null)
      if echo "${file_output}" | grep -q "CRLF"; then
        echo "  ✗ ERROR: ${script_name} todavía tiene CRLF!"
        echo "    Forzando conversión final..."
        tr -d '\r' < "${script}" > "${script}.final" 2>/dev/null && mv "${script}.final" "${script}"
        chmod 700 "${script}"
        echo "    ✓ Conversión final aplicada"
      else
        echo "  ✓ Sin CRLF detectado"
      fi
    fi
    
    # Verificar que sea ejecutable
    if [[ ! -x "${script}" ]]; then
      echo "  ⚠ Corrigiendo permisos..."
      chmod 700 "${script}"
    else
      echo "  ✓ Permisos correctos (700)"
    fi
    
    # Verificar que el archivo no esté vacío
    if [[ ! -s "${script}" ]]; then
      echo "  ✗ ERROR: ${script_name} está vacío!"
    else
      file_size=$(stat -c%s "${script}" 2>/dev/null || stat -f%z "${script}" 2>/dev/null || echo "unknown")
      echo "  ✓ Tamaño: ${file_size} bytes"
    fi
    
    echo ""
  done
  
  echo "[OK] Archivos copiados y configurados correctamente"

  # Instalar recursos
  local ASSETS_SRC="${SOURCE_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}/assets"
  if [[ -d "${ASSETS_SRC}" ]]; then
    # Copiar todos los assets, incluyendo icon.png si existe
    install -m 0644 "${ASSETS_SRC}"/* "${PLUGIN_DIR}/assets/" 2>/dev/null || true
    
    # Verificar si icon.png existe después de copiar
    if [[ -f "${PLUGIN_DIR}/assets/icon.png" ]]; then
      echo "[OK] icon.png copiado correctamente";
    elif [[ -f "${ASSETS_SRC}/icon.png" ]]; then
      # Si existe en el origen pero no se copió, copiarlo explícitamente
      install -m 0644 "${ASSETS_SRC}/icon.png" "${PLUGIN_DIR}/assets/icon.png"
      echo "[OK] icon.png copiado explícitamente";
    fi
    
    # Si solo hay SVG y NO hay PNG, intentar crear PNG
    if [[ -f "${PLUGIN_DIR}/assets/icon.svg" ]] && [[ ! -f "${PLUGIN_DIR}/assets/icon.png" ]]; then
      echo "[INFO] Generando icon.png desde icon.svg...";
      ICON_CREATED=0
      
      # Método 1: ImageMagick desde SVG (más confiable)
      if [[ ${ICON_CREATED} -eq 0 ]] && command -v convert >/dev/null 2>&1; then
        if convert -background none -density 300 "${PLUGIN_DIR}/assets/icon.svg" -resize 48x48 "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null; then
          ICON_SIZE=$(stat -c%s "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || stat -f%z "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || echo "0")
          if [[ ${ICON_SIZE} -gt 500 ]]; then
            chmod 644 "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
            echo "[OK] Icono PNG creado con ImageMagick desde SVG (${ICON_SIZE} bytes)";
            ICON_CREATED=1
          else
            rm -f "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
          fi
        fi
      fi
      
      # Método 2: rsvg-convert
      if [[ ${ICON_CREATED} -eq 0 ]] && command -v rsvg-convert >/dev/null 2>&1; then
        if rsvg-convert -w 48 -h 48 "${PLUGIN_DIR}/assets/icon.svg" -o "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null; then
          ICON_SIZE=$(stat -c%s "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || stat -f%z "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || echo "0")
          if [[ ${ICON_SIZE} -gt 500 ]]; then
            chmod 644 "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
            echo "[OK] Icono PNG creado con rsvg-convert (${ICON_SIZE} bytes)";
            ICON_CREATED=1
          else
            rm -f "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
          fi
        fi
      fi
      
      # Método 3: Inkscape
      if [[ ${ICON_CREATED} -eq 0 ]] && command -v inkscape >/dev/null 2>&1; then
        if inkscape --export-type=png --export-filename="${PLUGIN_DIR}/assets/icon.png" --export-width=48 --export-height=48 "${PLUGIN_DIR}/assets/icon.svg" 2>/dev/null; then
          ICON_SIZE=$(stat -c%s "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || stat -f%z "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || echo "0")
          if [[ ${ICON_SIZE} -gt 500 ]]; then
            chmod 644 "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
            echo "[OK] Icono PNG creado con Inkscape (${ICON_SIZE} bytes)";
            ICON_CREATED=1
          else
            rm -f "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
          fi
        fi
      fi
      
      # Método 4: Crear PNG básico con ImageMagick desde cero (48x48) - fallback
      if [[ ${ICON_CREATED} -eq 0 ]] && command -v convert >/dev/null 2>&1; then
        if convert -size 48x48 xc:transparent \
          -fill '#1e40af' -draw 'roundrectangle 6,6 42,42 3,3' \
          -fill white -stroke white -strokewidth 1.5 \
          -draw 'line 9,16 39,16' \
          -draw 'line 9,21 36,21' \
          -draw 'line 9,26 39,26' \
          -fill white -draw 'circle 37,10 42,10' \
          -fill '#1e40af' -draw 'circle 37,10 40,10' \
          "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null; then
          ICON_SIZE=$(stat -c%s "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || stat -f%z "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || echo "0")
          if [[ ${ICON_SIZE} -gt 500 ]]; then
            chmod 644 "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
            echo "[OK] Icono PNG básico creado con ImageMagick (48x48, ${ICON_SIZE} bytes)";
            ICON_CREATED=1
          else
            rm -f "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true
          fi
        fi
      fi
      
      if [[ ${ICON_CREATED} -eq 0 ]]; then
        echo "[WARN] No se pudo crear icon.png desde icon.svg.";
        echo "[WARN] Instala ImageMagick o librsvg:";
        echo "[WARN]   yum install ImageMagick";
        echo "[WARN]   o";
        echo "[WARN]   yum install librsvg2-tools";
      fi
    fi
  fi
  
  local CONFIG_SRC="${SOURCE_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}/config/log_sources.json"
  if [[ -f "${CONFIG_SRC}" ]]; then
    install -m 0644 "${CONFIG_SRC}" "${PLUGIN_DIR}/config/log_sources.json"
  fi
  
  local LIB_SRC="${SOURCE_DIR}/whostmgr/docroot/cgi/${PLUGIN_NAME}/lib/LogReader.pm"
  if [[ -f "${LIB_SRC}" ]]; then
    install -m 0644 "${LIB_SRC}" "${PLUGIN_DIR}/lib/LogReader.pm"
  fi
  
  # Copiar archivo VERSION al directorio del plugin
  local VERSION_SRC="${SOURCE_DIR}/VERSION"
  if [[ -f "${VERSION_SRC}" ]]; then
    install -m 0644 "${VERSION_SRC}" "${PLUGIN_DIR}/VERSION"
    echo "[OK] Archivo VERSION copiado"
  else
    echo "[WARN] Archivo VERSION no encontrado en ${VERSION_SRC}"
  fi
  
  # Actualizar BASE_DIR para las verificaciones posteriores
  BASE_DIR="${PLUGIN_DIR}"
  
  # Instalar archivo dynamicui como alternativa
  DYNAMICUI_DIR="/usr/local/cpanel/whostmgr/docroot/addon_plugins"
  local DYNAMICUI_SRC="${SOURCE_DIR}/whostmgr/docroot/addon_plugins/${PLUGIN_NAME}.dynamicui"
  if [[ -d "${DYNAMICUI_DIR}" ]] && [[ -f "${DYNAMICUI_SRC}" ]]; then
    echo "[INFO] Instalando archivo dynamicui en ${DYNAMICUI_DIR}";
    install -m 0644 "${DYNAMICUI_SRC}" "${DYNAMICUI_DIR}/${PLUGIN_NAME}.dynamicui"
  fi
  
  # Copiar icono a addon_plugins/ según documentación de cPanel (48x48 PNG)
  # Esta sección no debe causar fallo del script si el icono no se puede copiar
  set +e  # Desactivar exit on error temporalmente para esta sección
  echo "[INFO] Verificando icono para addon_plugins/...";
  echo "[DEBUG] PLUGIN_DIR: ${PLUGIN_DIR}";
  echo "[DEBUG] DYNAMICUI_DIR: ${DYNAMICUI_DIR}";
  echo "[DEBUG] PLUGIN_NAME: ${PLUGIN_NAME}";
  
  if [[ -f "${PLUGIN_DIR}/assets/icon.png" ]]; then
    echo "[INFO] Icono encontrado en ${PLUGIN_DIR}/assets/icon.png";
    ls -lh "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || true;
    echo "[INFO] Copiando icono a addon_plugins/...";
    
    # Asegurar que el directorio existe
    if ! install -d "${DYNAMICUI_DIR}" 2>/dev/null; then
      echo "[WARN] No se pudo crear directorio ${DYNAMICUI_DIR}";
    fi
    
    # Verificar tamaño del icono antes de copiar
    ICON_SIZE=$(stat -c%s "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || stat -f%z "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || echo "0")
    if [[ ${ICON_SIZE} -lt 500 ]]; then
      echo "[WARN] Icono en assets/ es demasiado pequeño (${ICON_SIZE} bytes), puede estar corrupto";
      echo "[INFO] Intentando regenerar desde SVG...";
      # Intentar regenerar desde SVG si existe
      if [[ -f "${PLUGIN_DIR}/assets/icon.svg" ]] && command -v convert >/dev/null 2>&1; then
        if convert -background none -density 300 -resize 48x48! "${PLUGIN_DIR}/assets/icon.svg" "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null; then
          ICON_SIZE=$(stat -c%s "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || stat -f%z "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null || echo "0")
          echo "[OK] Icono regenerado desde SVG (${ICON_SIZE} bytes)";
        fi
      fi
    fi
    
    # Redimensionar a 48x48 si es necesario y copiar
    if command -v convert >/dev/null 2>&1; then
      echo "[DEBUG] Usando convert para redimensionar a 48x48...";
      if convert -background none -resize 48x48! "${PLUGIN_DIR}/assets/icon.png" "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>&1; then
        chmod 644 "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true
        chown root:root "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true
        FINAL_SIZE=$(stat -c%s "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || stat -f%z "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || echo "0")
        echo "[OK] Icono copiado a ${DYNAMICUI_DIR}/${PLUGIN_NAME}.png (48x48, ${FINAL_SIZE} bytes)";
        ls -lh "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true;
      else
        # Si convert falla, intentar copiar directamente
        echo "[WARN] No se pudo redimensionar con convert, copiando directamente...";
        if install -m 0644 "${PLUGIN_DIR}/assets/icon.png" "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>&1; then
          chown root:root "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true
          echo "[OK] Icono copiado a ${DYNAMICUI_DIR}/${PLUGIN_NAME}.png";
          ls -lh "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true;
        else
          echo "[WARN] No se pudo copiar icono a addon_plugins/ (no crítico)";
        fi
      fi
    else
      # Si no hay convert, copiar directamente (asumiendo que ya es 48x48)
      echo "[DEBUG] No hay convert, copiando directamente...";
      if install -m 0644 "${PLUGIN_DIR}/assets/icon.png" "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>&1; then
        chown root:root "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true
        echo "[OK] Icono copiado a ${DYNAMICUI_DIR}/${PLUGIN_NAME}.png";
        ls -lh "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true;
      else
        echo "[WARN] No se pudo copiar icono a addon_plugins/ (no crítico)";
      fi
    fi
    
    # Verificar que el icono se copió correctamente
    if [[ -f "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" ]]; then
      echo "[OK] Verificación: Icono existe en ${DYNAMICUI_DIR}/${PLUGIN_NAME}.png";
      file "${DYNAMICUI_DIR}/${PLUGIN_NAME}.png" 2>/dev/null || true;
    else
      echo "[WARN] Verificación: Icono NO existe en ${DYNAMICUI_DIR}/${PLUGIN_NAME}.png";
    fi
  else
    echo "[WARN] No se encontró icon.png en ${PLUGIN_DIR}/assets/icon.png";
    echo "[DEBUG] Contenido de ${PLUGIN_DIR}/assets/:";
    ls -la "${PLUGIN_DIR}/assets/" 2>/dev/null || echo "  Directorio no existe";
  fi
  set -e  # Reactivar exit on error
}

rebuild_whm_menu() {
  echo "[INFO] Regenerando menú dinámico de WHM...";
  
  # Regenerar sprites de cPanel (importante para iconos)
  if [[ -x /usr/local/cpanel/bin/rebuild_sprites ]]; then
    /usr/local/cpanel/bin/rebuild_sprites >/dev/null 2>&1
    echo "[OK] Sprites regenerados";
  fi
  
  # Intentar rebuild_whm_chrome primero (similar a CSF)
  if [[ -x /usr/local/cpanel/bin/rebuild_whm_chrome ]]; then
    /usr/local/cpanel/bin/rebuild_whm_chrome >/dev/null 2>&1
    echo "[OK] Menú regenerado con rebuild_whm_chrome";
  fi
  
  if [[ -x /usr/local/cpanel/bin/rebuild_whm_dynamicui ]]; then
    /usr/local/cpanel/bin/rebuild_whm_dynamicui >/dev/null 2>&1
    echo "[OK] Menú regenerado con rebuild_whm_dynamicui";
    return 0;
  fi

  echo "[INFO] En cPanel 130, el menú se regenera automáticamente al reiniciar cpsrvd";
}

register_app() {
  # Intentar usar AppConfig primero
  echo "[INFO] Registrando AppConfig principal en ${APP_CONFIG_DST}";
  local APPCONFIG_SRC="${SOURCE_DIR}/appconfig/mlv.conf"
  if [[ ! -f "${APPCONFIG_SRC}" ]]; then
    echo "[ERROR] No se encontró AppConfig en: ${APPCONFIG_SRC}" >&2;
    exit 1;
  fi
  install -m 0600 "${APPCONFIG_SRC}" "${APP_CONFIG_DST}"
  chown root:root "${APP_CONFIG_DST}"
  
  echo "[INFO] Verificando que los archivos existen antes de registrar...";
  if [[ ! -f "${BASE_DIR}/mlv.cgi" ]]; then
    echo "[ERROR] mlv.cgi no existe en ${BASE_DIR}/mlv.cgi";
    exit 1;
  fi
  
  echo "[INFO] Verificando que el icono existe...";
  # Verificar icono PNG primero (preferido)
  if [[ -f "${PLUGIN_DIR}/assets/icon.png" ]]; then
    echo "[OK] Icono PNG encontrado en ${PLUGIN_DIR}/assets/icon.png";
    ls -la "${PLUGIN_DIR}/assets/icon.png";
  elif [[ -f "${PLUGIN_DIR}/assets/icon.svg" ]]; then
    echo "[OK] Icono SVG encontrado en ${PLUGIN_DIR}/assets/icon.svg";
    echo "[INFO] Convirtiendo SVG a PNG para mejor compatibilidad...";
    # Intentar convertir SVG a PNG si hay herramientas disponibles
    if command -v convert >/dev/null 2>&1; then
      convert "${PLUGIN_DIR}/assets/icon.svg" "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null && \
        echo "[OK] Icono convertido a PNG" || echo "[WARN] No se pudo convertir a PNG";
    elif command -v rsvg-convert >/dev/null 2>&1; then
      rsvg-convert -w 64 -h 64 "${PLUGIN_DIR}/assets/icon.svg" -o "${PLUGIN_DIR}/assets/icon.png" 2>/dev/null && \
        echo "[OK] Icono convertido a PNG" || echo "[WARN] No se pudo convertir a PNG";
    else
      echo "[WARN] No hay herramientas para convertir SVG a PNG, usando SVG";
    fi
  else
    echo "[WARN] No se encontró icono en ${PLUGIN_DIR}/assets/";
    echo "[INFO] Verificando contenido de assets:";
    ls -la "${PLUGIN_DIR}/assets/" 2>/dev/null || echo "  Directorio assets no existe";
    echo "[INFO] Comparando con CSF:";
    if [[ -f "/var/cpanel/apps/csf.conf" ]]; then
      echo "CSF AppConfig icon:";
      grep -i "icon" /var/cpanel/apps/csf.conf || echo "  CSF no tiene icono configurado";
    fi
  fi
  
  echo "[INFO] Verificando registro del plugin principal...";
  if /usr/local/cpanel/bin/register_appconfig "${APP_CONFIG_DST}" 2>&1; then
    echo "[OK] Plugin principal registrado correctamente con AppConfig";
  else
    echo "[WARN] Falló el registro del plugin principal con AppConfig";
  fi
  
  # NOTA: Solo registramos mlv.cgi como AppConfig principal
  # porque ahora mlv.cgi maneja todo internamente con parámetros API
  # Esto evita problemas con el wrapper de cPanel y scripts auxiliares
  echo "[INFO] Solo mlv.cgi requiere registro como AppConfig";
  echo "[INFO] Todas las solicitudes se manejan a través de mlv.cgi con parámetros API";
  
  rebuild_whm_menu
  
  # Verificar que el registro fue exitoso
  echo "[INFO] Verificando instalación final...";
  if [[ ! -f "${BASE_DIR}/${PLUGIN_NAME}.cgi" ]]; then
    echo "[ERROR] ${PLUGIN_NAME}.cgi no existe después de la instalación" >&2;
    exit 1;
  fi
  
  if [[ ! -f "${APP_CONFIG_DST}" ]]; then
    echo "[ERROR] AppConfig no existe después de la instalación" >&2;
    exit 1;
  fi
  
  # Verificar que el script se puede ejecutar
  local TEST_OUTPUT
  local TEST_EXIT
  set +e
  TEST_OUTPUT=$(/usr/local/cpanel/3rdparty/bin/perl "${BASE_DIR}/${PLUGIN_NAME}.cgi" 2>&1)
  TEST_EXIT=$?
  set -e

  local TEST_HEADER
  TEST_HEADER=$(printf '%s
' "${TEST_OUTPUT}" | head -n 1)

  if [[ ${TEST_EXIT} -eq 0 ]] && echo "${TEST_HEADER}" | grep -q "Content-type"; then
    echo "[OK] El script ${PLUGIN_NAME}.cgi se ejecuta correctamente";
  else
    echo "[WARN] El script ${PLUGIN_NAME}.cgi no produce salida válida al ejecutarse directamente";
    echo "[DEBUG] Salida (primeras líneas):";
    printf '%s
' "${TEST_OUTPUT}" | head -n 20
  fi
  
  echo "[OK] Archivos instalados correctamente";
  echo "[INFO] URL del plugin: /cgi/${PLUGIN_NAME}/${PLUGIN_NAME}.cgi";
  echo "[INFO] Estructura: Igual a CSF - script en /cgi/${PLUGIN_NAME}/${PLUGIN_NAME}.cgi";
  echo "[INFO] Para verificar la instalación, ejecuta: ./verify_installation.sh";
}

restart_services() {
  echo "[INFO] Reiniciando servicios de cPanel para aplicar cambios...";
  
  # En cPanel 130, necesitamos reiniciar cpsrvd para que el menú se actualice
  # Usar timeout corto (15 segundos) para evitar que se quede colgado
  # Similar a CSF: timeout corto y no bloquear si falla
  if command -v /scripts/restartsrv_cpsrvd >/dev/null 2>&1; then
    # Ejecutar en background con timeout para no bloquear
    (timeout 15 /scripts/restartsrv_cpsrvd >/dev/null 2>&1 || true) &
    echo "[OK] Servicio cpsrvd reiniciando en background (esto regenerará el menú de WHM)";
  elif command -v /scripts/restartsrv_whostmgrd >/dev/null 2>&1; then
    (timeout 15 /scripts/restartsrv_whostmgrd >/dev/null 2>&1 || true) &
    echo "[OK] Servicio whostmgrd reiniciando en background";
  else
    echo "[WARN] No se pudo reiniciar los servicios automáticamente";
    echo "[INFO] Ejecute manualmente: /scripts/restartsrv_cpsrvd";
  fi
}

unregister_app() {
  if [[ -f "${APP_CONFIG_DST}" ]]; then
    echo "[INFO] Eliminando AppConfig principal ${APP_CONFIG_DST}"
    /usr/local/cpanel/bin/unregister_appconfig "${APP_CONFIG_DST}" || true
    rm -f "${APP_CONFIG_DST}"
  fi

  local legacy_logs="/var/cpanel/apps/${PLUGIN_NAME}_logs.conf"
  if [[ -f "${legacy_logs}" ]]; then
    echo "[INFO] Eliminando AppConfig legacy (logs) ${legacy_logs}"
    /usr/local/cpanel/bin/unregister_appconfig "${legacy_logs}" || true
    rm -f "${legacy_logs}"
  fi

  local legacy_update="/var/cpanel/apps/${PLUGIN_NAME}_update.conf"
  if [[ -f "${legacy_update}" ]]; then
    echo "[INFO] Eliminando AppConfig legacy (update) ${legacy_update}"
    /usr/local/cpanel/bin/unregister_appconfig "${legacy_update}" || true
    rm -f "${legacy_update}"
  fi

  rebuild_whm_menu
}

remove_files() {
  local base_cgi_dir="/usr/local/cpanel/whostmgr/docroot/cgi"

  if [[ -f "${base_cgi_dir}/${PLUGIN_NAME}.cgi" ]]; then
    echo "[INFO] Eliminando script principal ${base_cgi_dir}/${PLUGIN_NAME}.cgi"
    rm -f "${base_cgi_dir}/${PLUGIN_NAME}.cgi"
  fi

  if [[ -d "${base_cgi_dir}/${PLUGIN_NAME}" ]]; then
    echo "[INFO] Eliminando directorio del plugin ${base_cgi_dir}/${PLUGIN_NAME}"
    rm -rf "${base_cgi_dir}/${PLUGIN_NAME}"
  fi

  if [[ -d "${BASE_DIR}" ]]; then
    echo "[INFO] Eliminando estructura antigua ${BASE_DIR}"
    rm -rf "${BASE_DIR}"
  fi

  local dynamicui_file="/usr/local/cpanel/whostmgr/docroot/addon_plugins/${PLUGIN_NAME}.dynamicui"
  if [[ -f "${dynamicui_file}" ]]; then
    echo "[INFO] Eliminando dynamicui legacy ${dynamicui_file}"
    rm -f "${dynamicui_file}"
  fi
}

plugin_installed() {
  [[ -f "${APP_CONFIG_DST}" ]] || [[ -d "/usr/local/cpanel/whostmgr/docroot/cgi/${PLUGIN_NAME}" ]]
}

perform_install() {
  echo "[INFO] Iniciando instalación v${PLUGIN_VERSION}"
  copy_files
  register_app
  if [[ ${SKIP_RESTART} -eq 0 ]]; then
    restart_services
  else
    echo "[INFO] Reinicio de servicios omitido (modo --no-restart)"
  fi
  echo "[OK] Instalación completada"
}

perform_upgrade() {
  echo "[INFO] Iniciando actualización v${PLUGIN_VERSION}"
  copy_files
  register_app
  if [[ ${SKIP_RESTART} -eq 0 ]]; then
    restart_services
  else
    echo "[INFO] Reinicio de servicios omitido (modo --no-restart)"
  fi
  echo "[OK] Actualización completada"
}

perform_uninstall() {
  echo "[INFO] Iniciando desinstalación"
  unregister_app
  remove_files
  if [[ ${SKIP_RESTART} -eq 0 ]]; then
    restart_services
  else
    echo "[INFO] Reinicio de servicios omitido (modo --no-restart)"
  fi
  echo "[OK] Desinstalación completada"
}

perform_reinstall() {
  echo "[INFO] Iniciando reinstalación"
  local original_skip=${SKIP_RESTART}
  SKIP_RESTART=1
  perform_uninstall
  SKIP_RESTART=${original_skip}
  perform_install
}

show_usage() {
  cat <<EOF
Uso: ./install.sh [opciones]

Opciones:
  --install        Fuerza una instalación limpia (equivalente a upgrade si ya existe)
  --upgrade        Actualiza archivos y AppConfig (por defecto si ya existe)
  --uninstall      Desinstala el plugin
  --reinstall      Desinstala y vuelve a instalar
  --no-restart     Omite el reinicio automático de cpsrvd
  -h, --help       Muestra esta ayuda

Sin argumentos, el script instalará el plugin si no está presente, o hará upgrade si ya existe.
EOF
}

ACTION=""
SKIP_RESTART=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) ACTION="install" ; shift ;;
    --upgrade) ACTION="upgrade" ; shift ;;
    --uninstall) ACTION="uninstall" ; shift ;;
    --reinstall) ACTION="reinstall" ; shift ;;
    --no-restart) SKIP_RESTART=1 ; shift ;;
    -h|--help) show_usage ; exit 0 ;;
    *) echo "[ERROR] Opción desconocida: $1" >&2 ; show_usage ; exit 1 ;;
  esac
done

require_root

if [[ -z "${ACTION}" ]]; then
  if plugin_installed; then
    ACTION="upgrade"
  else
    ACTION="install"
  fi
fi

case "${ACTION}" in
  install) perform_install ;;
  upgrade) perform_upgrade ;;
  uninstall) perform_uninstall ;;
  reinstall) perform_reinstall ;;
  *) echo "[ERROR] Acción desconocida: ${ACTION}" >&2 ; exit 1 ;;
esac

# Restaurar el directorio de trabajo original
cd "${ORIGINAL_PWD}" 2>/dev/null || true

if [[ ${SKIP_RESTART} -eq 1 ]]; then
  echo "[INFO] Nota: Los servicios no se reiniciaron automáticamente."
  echo "[INFO] Si el plugin no aparece en WHM, reinicie manualmente: /scripts/restartsrv_cpsrvd"
else
  echo "[INFO] Si el plugin no aparece en WHM:"
  echo "  1. Cierre sesión y vuelva a iniciar sesión en WHM"
  echo "  2. Limpie la caché del navegador (Ctrl+F5)"
  echo "  3. Acceda directamente a: https://$(hostname):2087/cgi/mlv/mlv.cgi"
fi

