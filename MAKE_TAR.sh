#!/bin/bash
# Script SIMPLE y ROBUSTO para crear el tar.gz
# Ejecutar desde DENTRO del directorio cpanel-multi-log-viewer

set -e

PLUGIN_NAME="cpanel-multi-log-viewer"

echo "=========================================="
echo "Creando ${PLUGIN_NAME}.tar.gz"
echo "=========================================="
echo ""

# Obtener el directorio donde está este script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "[1] Directorio del script: ${SCRIPT_DIR}"

# Verificar que estamos en el directorio correcto
if [[ ! -f "${SCRIPT_DIR}/install.sh" ]]; then
    echo "[ERROR] install.sh no encontrado en: ${SCRIPT_DIR}" >&2
    exit 1
fi

if [[ ! -d "${SCRIPT_DIR}/whostmgr" ]]; then
    echo "[ERROR] whostmgr/ no encontrado en: ${SCRIPT_DIR}" >&2
    exit 1
fi

echo "[2] ✓ Estructura del plugin verificada"
echo ""

# Obtener el directorio padre
PARENT_DIR="$(dirname "${SCRIPT_DIR}")"
OUTPUT_FILE="${PARENT_DIR}/${PLUGIN_NAME}.tar.gz"

echo "[3] Directorio padre: ${PARENT_DIR}"
echo "[4] Archivo de salida: ${OUTPUT_FILE}"
echo ""

# Verificar que el directorio padre existe
if [[ ! -d "${PARENT_DIR}" ]]; then
    echo "[ERROR] El directorio padre no existe: ${PARENT_DIR}" >&2
    exit 1
fi

# Verificar que podemos escribir en el directorio padre
if [[ ! -w "${PARENT_DIR}" ]]; then
    echo "[ERROR] No se puede escribir en: ${PARENT_DIR}" >&2
    exit 1
fi

# Eliminar el tar.gz anterior si existe
if [[ -f "${OUTPUT_FILE}" ]]; then
    echo "[5] Eliminando archivo anterior: ${OUTPUT_FILE}"
    rm -f "${OUTPUT_FILE}"
fi

# Cambiar al directorio padre
echo "[6] Cambiando al directorio padre..."
cd "${PARENT_DIR}" || {
    echo "[ERROR] No se pudo cambiar al directorio: ${PARENT_DIR}" >&2
    exit 1
}

echo "[7] Directorio actual: $(pwd)"

# Verificar que el directorio del plugin existe aquí
if [[ ! -d "${PLUGIN_NAME}" ]]; then
    echo "[ERROR] No se encontró el directorio ${PLUGIN_NAME} en $(pwd)" >&2
    echo "[ERROR] Contenido del directorio actual:" >&2
    ls -la | head -10 >&2
    exit 1
fi

echo "[8] ✓ Directorio ${PLUGIN_NAME} encontrado"
echo ""

# Crear el tar.gz con exclusión de archivos innecesarios
echo "[9] Creando tar.gz (excluyendo archivos temporales)..."
echo ""

# Crear archivo temporal con patrones de exclusión para mejor compatibilidad
EXCLUDE_FILE=$(mktemp 2>/dev/null || echo "/tmp/tar_exclude_$$.txt")
cat > "${EXCLUDE_FILE}" << 'EOF'
.git
.gitignore
.DS_Store
*.tar.gz
*.tar
MAKE_TAR.sh
*.log
test_*.sh
check_*.sh
create_*.sh
diagnose*.sh
fix_*.sh
verify_*.sh
deep_*.sh
debug_*.sh
apply_*.sh
*_TAR.sh
*_PACKAGE.sh
*.py
*TROUBLESHOOTING*.md
*INSTRUCCIONES*.md
*PACKAGE*.md
*QUICK*.md
whostmgr/docroot/cgi/*.tar.gz
whostmgr/docroot/cgi/multi_log_viewer
whostmgr/docroot/cgi/mlv/assets/create_*.sh
whostmgr/docroot/cgi/mlv/assets/generate_*.sh
whostmgr/docroot/cgi/mlv/assets/*.py
whostmgr/docroot/cgi/mlv/*.php
whostmgr/docroot/cgi/mlv/logs.cgi
whostmgr/docroot/cgi/mlv/update.cgi
appconfig/multi_log_viewer*.conf
test.tar
EOF

# Intentar usar compresión rápida si está disponible, sino usar la por defecto
if command -v gzip >/dev/null 2>&1; then
    if tar --force-local -czf "${OUTPUT_FILE}" --exclude-from="${EXCLUDE_FILE}" "${PLUGIN_NAME}/" 2>/dev/null; then
        echo "[10] ✓ Comando tar ejecutado exitosamente"
    else
        # Fallback: intentar sin exclusiones si falla
        echo "[WARN] Fallando a método sin exclusiones..." >&2
        tar --force-local -czf "${OUTPUT_FILE}" "${PLUGIN_NAME}/"
    fi
else
    # En Windows o sistemas sin gzip, usar tar estándar
    tar --force-local -czf "${OUTPUT_FILE}" --exclude-from="${EXCLUDE_FILE}" "${PLUGIN_NAME}/" 2>/dev/null || \
    tar --force-local -czf "${OUTPUT_FILE}" "${PLUGIN_NAME}/"
fi

# Limpiar archivo temporal
rm -f "${EXCLUDE_FILE}" 2>/dev/null || true

# Verificar que el archivo se creó
if [[ ! -f "${OUTPUT_FILE}" ]]; then
    echo "[ERROR] El archivo no se creó: ${OUTPUT_FILE}" >&2
    echo "[ERROR] Directorio actual: $(pwd)" >&2
    echo "[ERROR] Listando archivos en el directorio:" >&2
    ls -la | grep -i tar >&2 || echo "No se encontraron archivos tar" >&2
    exit 1
fi

FILE_SIZE=$(du -h "${OUTPUT_FILE}" 2>/dev/null | cut -f1 || echo "unknown")
echo "[11] ✓ Archivo creado: ${OUTPUT_FILE}"
echo "     Tamaño: ${FILE_SIZE}"
echo ""

# Verificar la estructura
echo "[12] Verificando estructura del tar.gz..."
FIRST_ENTRY=$(tar -tzf "${OUTPUT_FILE}" 2>/dev/null | head -1 | tr -d '\n' || echo "")

if [[ -z "${FIRST_ENTRY}" ]]; then
    echo "[ERROR] No se pudo leer el contenido del tar.gz" >&2
    exit 1
fi

echo "     Primera entrada: '${FIRST_ENTRY}'"
echo ""

if [[ "${FIRST_ENTRY}" == "${PLUGIN_NAME}/" ]] || [[ "${FIRST_ENTRY}" == "${PLUGIN_NAME}" ]]; then
    echo "=========================================="
    echo "✓ CORRECTO: El tar.gz está bien empaquetado"
    echo "=========================================="
    echo ""
    echo "Archivo: ${OUTPUT_FILE}"
    echo "Tamaño: ${FILE_SIZE}"
    echo ""
    echo "Primeras 5 entradas:"
    tar -tzf "${OUTPUT_FILE}" | head -5
    echo ""
    echo "✓ Al extraerlo, se creará el directorio: ${PLUGIN_NAME}/"
    echo "✓ Los archivos NO quedarán sueltos."
else
    echo "[ERROR] La estructura es INCORRECTA" >&2
    echo "Primera entrada: '${FIRST_ENTRY}'" >&2
    echo "Debería ser: '${PLUGIN_NAME}/'" >&2
    echo ""
    echo "Todas las entradas:" >&2
    tar -tzf "${OUTPUT_FILE}" | head -10 >&2
    exit 1
fi


