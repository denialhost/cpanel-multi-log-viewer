#!/usr/local/cpanel/3rdparty/bin/perl
#WHMADDON:mlv:Multi Log Viewer

use strict;
use warnings;

use CGI;
use Encode qw(encode);
use FindBin;
use JSON::PP;

use lib "$FindBin::Bin/lib";

# Manejo de errores global (similar a logs.cgi)
$SIG{__DIE__} = sub {
    my $error = shift;
    # Intentar determinar si es una solicitud API
    my $cgi = eval { CGI->new } || undef;
    my $api_action = $cgi ? ($cgi->param('api') || '') : '';
    
    if ($api_action eq 'logs' || $api_action eq 'update') {
        print "Content-type: application/json; charset=utf-8\n\n";
        print encode_json({ 
            status => 'error', 
            message => 'Error interno del servidor',
            detail => $error 
        });
    } else {
        print "Content-type: text/html; charset=utf-8\n\n";
        print "<!DOCTYPE html><html><head><title>Error</title></head><body>";
        print "<h1>Error 500</h1>";
        print "<p>Error interno del servidor:</p>";
        my $escaped_error = $error;
        $escaped_error =~ s/&/&amp;/g;
        $escaped_error =~ s/</&lt;/g;
        $escaped_error =~ s/>/&gt;/g;
        $escaped_error =~ s/"/&quot;/g;
        $escaped_error =~ s/'/&#39;/g;
        print "<pre>" . $escaped_error . "</pre>";
        print "</body></html>";
    }
    exit 1;
};

# Cargar LogReader con manejo de errores
my $LogReader_loaded = 0;
eval {
    require LogReader;
    $LogReader_loaded = 1;
};
if ($@) {
    # Si no se puede cargar LogReader, mostrar error apropiado
    my $cgi = CGI->new;
    my $api_action = $cgi->param('api') || '';
    if ($api_action eq 'logs' || $api_action eq 'update') {
        print $cgi->header('application/json; charset=utf-8');
        print encode_json({ 
            status => 'error', 
            message => 'Error al cargar el módulo LogReader',
            detail => $@ 
        });
        exit;
    }
    # Si no es API, continuar pero sin funcionalidad de logs
}

# Detectar si es una solicitud API (logs o update)
my $cgi = CGI->new;
my $api_action = $cgi->param('api') || '';
my $is_api_request = ($api_action eq 'logs' || $api_action eq 'update');

# Si es una solicitud API, manejar como JSON
if ($is_api_request) {
    eval {
        if ($api_action eq 'logs') {
            # Manejar solicitudes de logs (equivalente a logs.cgi)
            print $cgi->header('application/json; charset=utf-8');
            
            my $config_path = "$FindBin::Bin/config/log_sources.json";
            my $reader;
            eval {
                $reader = LogReader->new( config_path => $config_path );
            };
            if ($@ || !$reader) {
                print encode_json({ 
                    status => 'error', 
                    message => 'Error al inicializar LogReader',
                    detail => $@ || 'No se pudo crear instancia de LogReader'
                });
                exit;
            }
            
            my $action = $cgi->param('action') || 'list';
            
            if ($action eq 'list') {
                my $logs = $reader->list_logs;
                print encode_json({ status => 'ok', data => $logs });
                exit;
            }
            
            if ($action eq 'tail') {
                my $id     = $cgi->param('id') // '';
                my $lines  = $cgi->param('lines');
                my $search = $cgi->param('search');
                my $case   = $cgi->param('case');
                
                $lines = 200 unless defined $lines && $lines =~ /^\d{1,4}$/ && $lines > 0;
                $search = '' unless defined $search;
                my $case_sensitive = ($case && $case eq '1') ? 1 : 0;
                
                my $result = $reader->tail_log(
                    id             => $id,
                    lines          => $lines,
                    search         => $search,
                    case_sensitive => $case_sensitive,
                );
                
                print encode_json($result);
                exit;
            }
            
            if ($action eq 'search_all') {
                my $lines  = $cgi->param('lines');
                my $search = $cgi->param('search');
                my $case   = $cgi->param('case');
                
                my $lines_limit = 500;
                if (defined $lines && $lines =~ /^\d{1,4}$/ && $lines > 0) {
                    $lines_limit = $lines > 2000 ? 2000 : $lines;
                }
                
                my $case_sensitive = ($case && $case eq '1') ? 1 : 0;
                
                my $result = $reader->search_all_logs(
                    search         => defined $search ? $search : '',
                    lines          => $lines_limit,
                    case_sensitive => $case_sensitive,
                );
                
                print encode_json($result);
                exit;
            }
            
            print encode_json({ status => 'error', message => 'Acción no soportada' });
            exit;
        }
        
        if ($api_action eq 'update') {
            # Manejar solicitudes de update (equivalente a update.cgi)
            print $cgi->header('application/json; charset=utf-8');
            
            # Solo permitir a root
            my $remote_user = $ENV{REMOTE_USER} || $ENV{HTTP_REMOTE_USER} || '';
            if ($remote_user ne 'root') {
                print encode_json({ 
                    status => 'error', 
                    message => 'Solo el usuario root puede actualizar el plugin' 
                });
                exit;
            }
            
            my $action = $cgi->param('action') || 'check';
            my $update_url = $cgi->param('url') || 'https://dev.denialhost.com/cpanel-multi-log-viewer.tar.gz';
            
            if ($action eq 'check') {
                my $current_version = 'unknown';
                my $version_file = "$FindBin::Bin/.version";
                if (-f $version_file) {
                    open my $fh, '<', $version_file or die "No se pudo leer $version_file: $!";
                    $current_version = <$fh>;
                    chomp $current_version;
                    close $fh;
                }
                
                print encode_json({ 
                    status => 'ok', 
                    current_version => $current_version,
                    update_url => $update_url
                });
                exit;
            }
            
            if ($action eq 'update') {
                # Prevenir ejecuciones concurrentes usando un lock file
                my $lock_file = "/tmp/mlv_update.lock";
                if (-f $lock_file) {
                    # Verificar si el lock es antiguo (más de 10 minutos = proceso colgado)
                    my $lock_age = time() - (stat($lock_file))[9];
                    if ($lock_age > 600) {
                        # Lock antiguo, eliminarlo
                        unlink $lock_file;
                    } else {
                        print encode_json({ 
                            status => 'error', 
                            message => 'Ya hay una actualización en progreso',
                            detail => "Por favor espere a que termine la actualización anterior o elimine el lock: rm -f $lock_file"
                        });
                        exit;
                    }
                }
                
                # Crear lock file
                open my $lock_fh, '>', $lock_file or die "No se pudo crear lock file: $!";
                print $lock_fh $$ . "\n" . time() . "\n";
                close $lock_fh;
                
                # Asegurar que el lock se elimine al salir (incluso por error)
                eval {
                    require File::Temp;
                    require File::Copy;
                    File::Temp->import(qw(tempdir));
                    File::Copy->import(qw(copy));
                    
                    my $temp_dir = tempdir(CLEANUP => 1);
                    my $tar_file = "$temp_dir/plugin.tar.gz";
                
                # Descargar el archivo
                my $download_cmd = "curl -k -L -o '$tar_file' '$update_url' 2>&1";
                my $download_output = `$download_cmd`;
                my $download_exit = $? >> 8;
                
                if ($download_exit != 0 || !-f $tar_file) {
                    my $detail = "URL: $update_url\n";
                    $detail .= "Comando: $download_cmd\n";
                    $detail .= "Código de salida: $download_exit\n";
                    $detail .= "Salida: $download_output\n";
                    $detail .= "Archivo existe: " . (-f $tar_file ? "Sí" : "No") . "\n";
                    
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error al descargar el archivo',
                        detail => $detail 
                    });
                    exit;
                }
                
                # Verificar que el archivo descargado no esté vacío
                my $tar_size = -s $tar_file;
                if (!$tar_size || $tar_size < 100) {
                    print encode_json({ 
                        status => 'error', 
                        message => 'El archivo descargado está vacío o es muy pequeño',
                        detail => "Tamaño: $tar_size bytes"
                    });
                    exit;
                }
                
                # Verificar que el directorio temporal existe
                if (!-d $temp_dir) {
                    print encode_json({ 
                        status => 'error', 
                        message => 'El directorio temporal no existe',
                        detail => "Directorio: $temp_dir"
                    });
                    exit;
                }
                
                # Verificar que el tar.gz no contiene rutas absolutas peligrosas
                my $check_cmd = "tar -tzf '$tar_file' 2>&1 | head -10";
                my $check_output = `$check_cmd`;
                if ($check_output =~ m{^/}) {
                    print encode_json({ 
                        status => 'error', 
                        message => 'El archivo tar contiene rutas absolutas. Esto es peligroso y no se permitirá.',
                        detail => "Primeras rutas en el tar:\n$check_output\n\nEl tar.gz debe contener solo rutas relativas."
                    });
                    exit;
                }
                
                # Extraer el archivo de forma segura usando -C para especificar el directorio
                # Esto evita que tar se ejecute desde el directorio actual si cd falla
                my $extract_cmd = "tar -xzf '$tar_file' -C '$temp_dir' 2>&1";
                my $extract_output = `$extract_cmd`;
                my $extract_exit = $? >> 8;
                
                # Debug: Listar contenido después de extraer
                my $list_cmd = "cd '$temp_dir' && find . -maxdepth 2 -type d 2>&1 | head -20";
                my $list_output = `$list_cmd`;
                
                if ($extract_exit != 0) {
                    my $detail = "Comando: $extract_cmd\n";
                    $detail .= "Código de salida: $extract_exit\n";
                    $detail .= "Salida: $extract_output\n";
                    $detail .= "Tamaño del archivo: $tar_size bytes\n";
                    $detail .= "Contenido después de extraer:\n$list_output\n";
                    
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error al extraer el archivo',
                        detail => $detail 
                    });
                    exit;
                }
                
                # Agregar información de debug sobre la estructura extraída
                my $debug_extract = "Archivo extraído correctamente\n";
                $debug_extract .= "Contenido del directorio temporal:\n";
                $debug_extract .= $list_output;
                
                # Buscar el directorio del plugin
                # Primero verificar si install.sh está directamente en el directorio temporal (tar.gz mal empaquetado)
                my $plugin_dir = undef;
                my $debug_info = $debug_extract;
                $debug_info .= "\nBuscando directorio del plugin...\n";
                $debug_info .= "Directorio temporal: $temp_dir\n";
                
                # Verificar primero si install.sh está directamente en el directorio temporal
                if (-f "$temp_dir/install.sh") {
                    $plugin_dir = $temp_dir;
                    $debug_info .= "✓ install.sh encontrado directamente en el directorio temporal (tar.gz sin subdirectorio)\n";
                } else {
                    # Buscar en subdirectorios
                    $plugin_dir = "$temp_dir/cpanel-multi-log-viewer";
                    
                    # Listar contenido del directorio temporal
                    if (-d $temp_dir) {
                        opendir my $dh, $temp_dir or die "No se pudo abrir $temp_dir: $!";
                        my @entries = readdir $dh;
                        closedir $dh;
                        
                        $debug_info .= "Contenido de $temp_dir:\n";
                        foreach my $entry (@entries) {
                            next if $entry eq '.' || $entry eq '..';
                            my $path = "$temp_dir/$entry";
                            my $type = -d $path ? "DIR" : (-f $path ? "FILE" : "OTHER");
                            $debug_info .= "  - $entry ($type)\n";
                            
                            if (-d $path) {
                                # Verificar si contiene install.sh
                                if (-f "$path/install.sh") {
                                    $debug_info .= "    -> Contiene install.sh, usando este directorio\n";
                                    $plugin_dir = $path;
                                    last;
                                } else {
                                    # Buscar recursivamente en subdirectorios
                                    opendir my $subdh, $path or next;
                                    my @subentries = readdir $subdh;
                                    closedir $subdh;
                                    
                                    foreach my $subentry (@subentries) {
                                        next if $subentry eq '.' || $subentry eq '..';
                                        my $subpath = "$path/$subentry";
                                        if (-d $subpath && -f "$subpath/install.sh") {
                                            $debug_info .= "    -> Subdirectorio $subentry contiene install.sh\n";
                                            $plugin_dir = $subpath;
                                            last;
                                        }
                                    }
                                    last if $plugin_dir && -f "$plugin_dir/install.sh";
                                }
                            }
                        }
                    }
                }
                
                if (!$plugin_dir || !-f "$plugin_dir/install.sh") {
                    $debug_info .= "\nERROR: No se encontró install.sh en ningún directorio\n";
                    $debug_info .= "Plugin dir verificado: " . ($plugin_dir || "undef") . "\n";
                    $debug_info .= "Es directorio: " . ($plugin_dir && -d $plugin_dir ? "Sí" : "No") . "\n";
                    $debug_info .= "install.sh existe: " . ($plugin_dir && -f "$plugin_dir/install.sh" ? "Sí" : "No") . "\n";
                    
                    print encode_json({ 
                        status => 'error', 
                        message => 'No se encontró install.sh en el archivo descargado',
                        detail => $debug_info
                    });
                    exit;
                }
                
                $debug_info .= "\n✓ Directorio del plugin encontrado: $plugin_dir\n";
                
                # Guardar debug_info para uso posterior
                my $saved_debug = $debug_info;
                
                # Convertir CRLF a LF en install.sh si es necesario
                if (-f "$plugin_dir/install.sh") {
                    my $install_sh_content;
                    {
                        local $/;
                        open my $fh, '<', "$plugin_dir/install.sh" or die "No se pudo leer install.sh: $!";
                        $install_sh_content = <$fh>;
                        close $fh;
                    }
                    $install_sh_content =~ s/\r\n/\n/g;
                    $install_sh_content =~ s/\r/\n/g;
                    {
                        open my $fh, '>', "$plugin_dir/install.sh" or die "No se pudo escribir install.sh: $!";
                        print $fh $install_sh_content;
                        close $fh;
                    }
                    chmod 0755, "$plugin_dir/install.sh";
                }
                
                # Verificar que install.sh existe y es ejecutable
                if (!-f "$plugin_dir/install.sh") {
                    print encode_json({ 
                        status => 'error', 
                        message => 'No se encontró install.sh en el plugin',
                        detail => "Directorio: $plugin_dir"
                    });
                    exit;
                }
                
                # Verificar permisos y contenido de install.sh
                my $install_sh_size = -s "$plugin_dir/install.sh";
                if (!$install_sh_size || $install_sh_size == 0) {
                    print encode_json({ 
                        status => 'error', 
                        message => 'install.sh está vacío o no se puede leer',
                        detail => "Tamaño: $install_sh_size bytes"
                    });
                    exit;
                }
                
                # Debug: Log del comando que se va a ejecutar
                my $final_debug = $saved_debug;
                $final_debug .= "\nPlugin dir final: $plugin_dir\n";
                $final_debug .= "install.sh existe: " . (-f "$plugin_dir/install.sh" ? "Sí" : "No") . "\n";
                $final_debug .= "install.sh tamaño: $install_sh_size bytes\n";
                $final_debug .= "install.sh ejecutable: " . (-x "$plugin_dir/install.sh" ? "Sí" : "No") . "\n";
                
                # Ejecutar el script de instalación usando bash explícitamente
                # Similar a CSF: usar timeout corto (90 segundos) y deshabilitar reinicio de servicios
                # CSF no reinicia servicios durante actualizaciones web para evitar bucles
                
                # Usar alarm() de Perl como timeout adicional (más confiable que solo timeout del shell)
                local $SIG{ALRM} = sub { 
                    # Matar cualquier proceso hijo que pueda estar ejecutándose
                    system("pkill -f 'install.sh --no-restart' 2>/dev/null");
                    die "TIMEOUT: El proceso excedió 90 segundos\n";
                };
                alarm(90);  # 90 segundos máximo
                
                # Verificar si timeout está disponible
                my $has_timeout = system("which timeout >/dev/null 2>&1") == 0;
                my $install_cmd;
                
                if ($has_timeout) {
                    $install_cmd = "cd '$plugin_dir' && timeout 90 bash ./install.sh --no-restart 2>&1";
                } else {
                    # Fallback: ejecutar directamente (el alarm de Perl lo matará)
                    $install_cmd = "cd '$plugin_dir' && bash ./install.sh --no-restart 2>&1";
                }
                
                # Ejecutar con límites de recursos adicionales (similar a CSF)
                # ulimit -t limita el tiempo de CPU, ulimit -v limita memoria virtual
                if ($^O ne 'MSWin32') {
                    $install_cmd = "ulimit -t 90 -v 1048576 2>/dev/null; $install_cmd";
                }
                
                my $install_output = `$install_cmd`;
                my $install_exit = $? >> 8;
                
                alarm(0);  # Cancelar alarm
                
                # Verificar si hubo timeout (código 124, o si el output contiene indicios de timeout, o si $@ tiene TIMEOUT)
                if ($install_exit == 124 || $install_output =~ /timeout|TIMEOUT|killed|terminated/i || ($@ && $@ =~ /TIMEOUT/)) {
                    # Matar cualquier proceso hijo que pueda estar ejecutándose
                    system("pkill -f 'install.sh --no-restart' 2>/dev/null");
                    print encode_json({ 
                        status => 'error', 
                        message => 'El proceso de instalación excedió el tiempo límite (90 segundos)',
                        detail => 'El script de instalación tomó demasiado tiempo. Esto puede indicar un problema o un bucle infinito. Intente actualizar manualmente desde la línea de comandos.'
                    });
                    exit;
                }
                
                # Si el proceso fue terminado por límite de recursos (143 = SIGTERM, 137 = SIGKILL)
                if ($install_exit == 137 || $install_exit == 143) {
                    print encode_json({ 
                        status => 'error', 
                        message => 'El proceso de instalación fue terminado por límite de recursos',
                        detail => 'El script de instalación consumió demasiados recursos del sistema. Intente actualizar manualmente desde la línea de comandos.'
                    });
                    exit;
                }
                
                # Guardar versión (usar timestamp como versión)
                my $version_file = "$FindBin::Bin/.version";
                open my $fh, '>', $version_file or warn "No se pudo escribir $version_file: $!";
                if ($fh) {
                    print $fh time() . "\n";
                    close $fh;
                }
                
                # Limpiar la salida de install.sh (eliminar caracteres de control y normalizar)
                # Similar a CSF: limitar tamaño de salida para evitar problemas de memoria
                $install_output =~ s/\r//g;
                $install_output =~ s/[^\x20-\x7E\n\r\t]//g;
                
                # Limitar tamaño de salida (máximo 50KB para evitar problemas)
                if (length($install_output) > 50000) {
                    $install_output = substr($install_output, 0, 50000) . "\n... (salida truncada por tamaño)";
                }
                
                if ($install_exit != 0) {
                    my $detail = $final_debug . "\n--- Salida del script ---\n" . $install_output;
                    
                    # Limitar tamaño total del detalle (máximo 10KB)
                    if (length($detail) > 10000) {
                        $detail = substr($detail, 0, 10000) . "\n... (detalle truncado por tamaño)";
                    }
                    
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error al ejecutar el script de instalación',
                        detail => $detail,
                        exit_code => $install_exit,
                        debug => $final_debug
                    });
                    exit;
                }
                
                # Para respuesta exitosa, limitar salida a 5KB (similar a CSF)
                my $output = $install_output;
                if (length($output) > 5000) {
                    $output = substr($output, 0, 5000) . "\n... (salida truncada)";
                }
                
                print encode_json({ 
                    status => 'ok', 
                    message => 'Plugin actualizado correctamente. Nota: Los servicios no se reiniciaron automáticamente. Si el plugin no aparece, ejecute: /scripts/restartsrv_cpsrvd',
                    output => $output 
                });
                };
                
                # Eliminar lock file al finalizar (éxito o error)
                unlink $lock_file if -f $lock_file;
                
                if ($@) {
                    # Matar cualquier proceso hijo que pueda estar ejecutándose
                    system("pkill -f 'install.sh --no-restart' 2>/dev/null");
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error durante la actualización',
                        detail => $@ 
                    });
                }
                exit;
            }
            
            print encode_json({ status => 'error', message => 'Acción no soportada' });
            exit;
        }
    };
    
    if ($@) {
        print "Content-type: application/json; charset=utf-8\n\n";
        print encode_json({ 
            status => 'error', 
            message => 'Error al procesar la solicitud API',
            detail => $@ 
        });
        exit 1;
    }
}

# Si no es API, mostrar la interfaz HTML
eval {
    print "Content-type: text/html; charset=utf-8\n\n";

    # Detectar si estamos dentro de WHM (iframe) o en pantalla completa
    my $is_whm_frame = $ENV{HTTP_REFERER} && $ENV{HTTP_REFERER} =~ /\/cpsess/;
    my $is_whm_request = $ENV{REQUEST_URI} && $ENV{REQUEST_URI} =~ /\/cpsess/;

# Obtener la ruta base del script actual
my $script_name = $ENV{SCRIPT_NAME} || '/cgi/mlv/mlv.cgi';
    my $base_path = $script_name;
    $base_path =~ s/[^\/]+$//;  # Remover el nombre del archivo, dejar solo el directorio
    $base_path =~ s/\/$//;      # Remover la barra final si existe
    $base_path = $base_path || '/cgi/mlv';

    if ($is_whm_frame || $is_whm_request) {
    # Modo integrado en WHM: HTML mínimo pero con DOCTYPE
    print qq{<!DOCTYPE html>\n};
    print qq{<link rel="stylesheet" href="$base_path/assets/style.css" />\n};
    print qq{<div id="multi-log-viewer-container" class="whm-iframe-mode" style="width: 100%; height: 100%;">\n};
} else {
    # Modo pantalla completa: HTML completo
    print <<"HTML";
<!DOCTYPE html>
<html lang="es">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Multi Log Viewer</title>
    <link rel="stylesheet" href="$base_path/assets/style.css" />
  </head>
  <body class="fullscreen-mode">
HTML
    }

    print <<"HTML";
    <header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h1>Multi Log Viewer</h1>
          <p>Inspecciona logs de cPanel, Apache, Nginx y firewall desde un único lugar.</p>
        </div>
        <button id="show-update-btn" style="padding: 0.5rem 1rem; background: rgba(148, 163, 184, 0.2); border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 0.5rem; color: #e2e8f0; cursor: pointer; font-size: 0.85rem;">Actualizar Plugin</button>
      </div>
    </header>
    <main id="main-content">
      <aside id="logs-list">
        <div class="search">
          <input id="filter-input" type="text" placeholder="Filtrar por nombre" />
        </div>
        <ul id="logs"></ul>
      </aside>
      <section id="viewer">
        <div class="controls">
          <label for="lines-input">Últimas líneas:</label>
          <input id="lines-input" type="number" min="10" max="2000" value="200" />
          <label for="search-input">Buscar:</label>
          <div style="display: flex; gap: 0.3rem; align-items: center; position: relative;">
            <input id="search-input" type="text" placeholder="Expresión o texto" style="flex: 1;" />
            <button id="clear-search-btn" class="secondary" title="Limpiar búsqueda" style="padding: 0.45rem 0.8rem; min-width: 2rem; display: none; position: absolute; right: 0.3rem; background: rgba(239, 68, 68, 0.8); color: white; border: none;">✕</button>
          </div>
          <label class="checkbox">
            <input type="checkbox" id="case-checkbox" /> Sensible a mayúsculas
          </label>
          <button id="refresh-btn">Buscar</button>
          <button id="live-btn" class="secondary" title="Auto-refresh cada 5 segundos">Live</button>
          <button id="pause-btn" class="secondary" style="display: none;" title="Pausar auto-refresh">Pausar</button>
          <button id="search-all-btn" class="secondary">Buscar en todos</button>
        </div>
        <div id="status"></div>
        <pre id="log-output"><code>Seleccione un log para comenzar.</code></pre>
      </section>
    </main>
    <div id="update-panel" style="display: none;">
      <div class="update-content">
        <h2>Actualizar Plugin</h2>
        <p id="update-status">Verificando versión actual...</p>
        <div id="update-progress" style="display: none;">
          <div class="progress-bar">
            <div class="progress-fill"></div>
          </div>
          <p id="update-message"></p>
        </div>
        <div class="update-actions">
          <button id="update-btn" class="primary">Actualizar Ahora</button>
          <button id="cancel-update-btn">Cancelar</button>
        </div>
      </div>
    </div>
    <template id="log-item-template">
      <li class="log-item" data-id="">
        <div class="title"></div>
        <div class="subtitle"></div>
      </li>
    </template>
    <script>
      // Inyectar la ruta base en el JavaScript
      window.MLV_BASE = "$base_path";
    </script>
    <script src="$base_path/assets/app.js"></script>
HTML

    if ($is_whm_frame || $is_whm_request) {
        # Cerrar solo el div para modo iframe
        print "</div>\n";
    } else {
        # Cerrar HTML completo para modo pantalla completa
        print "  </body>\n</html>\n";
    }
};
if ($@) {
    # Si hay un error al generar HTML, mostrar error
    print "Content-type: text/html; charset=utf-8\n\n";
    print "<!DOCTYPE html><html><head><title>Error</title></head><body>";
    print "<h1>Error 500</h1>";
    print "<p>Error al generar la interfaz:</p>";
    my $escaped_error = $@;
    $escaped_error =~ s/&/&amp;/g;
    $escaped_error =~ s/</&lt;/g;
    $escaped_error =~ s/>/&gt;/g;
    $escaped_error =~ s/"/&quot;/g;
    $escaped_error =~ s/'/&#39;/g;
    print "<pre>" . $escaped_error . "</pre>";
    print "</body></html>";
    exit 1;
}
