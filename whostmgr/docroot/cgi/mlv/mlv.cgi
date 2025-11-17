#!/usr/local/cpanel/3rdparty/bin/perl
#WHMADDON:mlv:Multi Log Viewer

use strict;
use warnings;
use utf8;
use open qw(:std :utf8);

use CGI;
use Encode qw(encode decode decode_utf8 FB_CROAK);
use FindBin;
use JSON::PP;
use File::Basename qw(basename);
use File::stat;

use lib "$FindBin::Bin/lib";

# Manejo de errores global (similar a logs.cgi)
# IMPORTANTE: Este handler se ejecuta cuando hay un die() o error fatal
# Debe detectar si es API ANTES de imprimir cualquier cosa
$SIG{__DIE__} = sub {
    my $error = shift;
    binmode STDOUT, ':encoding(UTF-8)';
    # Intentar determinar si es una solicitud API SIN crear output
    # Usar eval para evitar que CGI->new cause output
    my $cgi = eval { CGI->new } || undef;
    my $api_action = '';
    if ($cgi) {
        eval {
            $api_action = $cgi->param('api') || '';
        };
        # Si falla, asumir que no es API
    }
    
    # Si es API, devolver JSON
    if ($api_action eq 'logs' || $api_action eq 'update') {
        # Asegurar que no hay output antes del JSON
        print "Content-type: application/json; charset=utf-8\n\n";
        eval {
            print encode_json({ 
                status => 'error', 
                message => 'Error interno del servidor',
                detail => $error 
            });
        };
        # Si encode_json falla, al menos intentar devolver algo
        if ($@) {
            print '{"status":"error","message":"Error interno del servidor","detail":"Error al codificar JSON"}' . "\n";
        }
    } else {
        # Si no es API, devolver HTML
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
    # IMPORTANTE: Crear CGI sin output previo
    my $cgi = eval { CGI->new } || CGI->new;
    my $api_action = $cgi->param('api') || '';
    if ($api_action eq 'logs' || $api_action eq 'update') {
        # Asegurar que no hay output antes del JSON
        print "Content-type: application/json; charset=utf-8\n\n";
        print encode_json({ 
            status => 'error', 
            message => 'Error al cargar el módulo LogReader',
            detail => $@ 
        });
        exit;
    }
    # Si no es API, continuar pero sin funcionalidad de logs
}

# Detectar si es una solicitud API (logs, update o changelog)
# IMPORTANTE: Crear CGI ANTES de cualquier output
my $cgi = eval { CGI->new } || CGI->new;
my $api_action = $cgi->param('api') || '';
my $is_api_request = ($api_action eq 'logs' || $api_action eq 'update' || $api_action eq 'changelog');


sub _install_process_running {
    my @checks = (
        qx{/bin/ps -eo pid,command | grep "timeout 90 bash ./install.sh --no-restart" | grep -v grep},
        qx{/bin/ps -eo pid,command | grep "bash ./install.sh --no-restart" | grep -v grep},
    );

    for my $output (@checks) {
        next unless defined $output;
        return 1 if $output =~ /install\.sh/;
    }
    return 0;
}

if (defined(my $download_id = $cgi->param('download'))) {
    eval {
        handle_download($download_id);
    };
    if ($@) {
        my $error = $@;
        $error =~ s/\s+$//;
        print "Status: 500 Internal Server Error\n";
        print "Content-type: text/plain; charset=utf-8\n\n";
        print "Error al preparar la descarga: $error\n";
    }
    exit;
}

# Si es una solicitud API, desactivar warnings para evitar output antes del JSON
# Y asegurar que no hay output antes del header JSON
if ($is_api_request) {
    $SIG{__WARN__} = sub {
        my ($msg) = @_;
        chomp $msg;
        warn "$msg\n";
    };
    binmode STDOUT, ':encoding(UTF-8)';
    print "Content-type: application/json; charset=utf-8\n\n";
    my $api_ok = eval {
        if ($api_action eq 'logs') {
            # Manejar solicitudes de logs (equivalente a logs.cgi)
            $| = 1;
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
            
            # Header JSON ya fue impreso arriba
            print encode_json({ status => 'error', message => 'Acción no soportada' });
            exit;
        }
        
        if ($api_action eq 'changelog') {
            # Endpoint para obtener el changelog (evita problemas de X-Frame-Options)
            my $changelog_url = 'https://raw.githubusercontent.com/denialhost/cpanel-multi-log-viewer/main/cpanel-multi-log-viewer-version.txt';
            
            eval {
                my $fetch_cmd = "curl -s -k -L --max-time 10 '$changelog_url' 2>/dev/null || wget -q -O - --no-check-certificate '$changelog_url' 2>/dev/null";
                my $remote_content = `$fetch_cmd`;
                
                if ($remote_content) {
                    # Decodificar y limpiar el contenido
                    my $decoded = eval { decode('UTF-8', $remote_content) };
                    if ($@) {
                        $decoded = eval { decode('ISO-8859-1', $remote_content) };
                    }
                    $decoded = $decoded // $remote_content;
                    $decoded =~ s/\r\n/\n/g;
                    $decoded =~ s/\r/\n/g;
                    
                    # Limpiar caracteres problemáticos
                    $decoded =~ s/[\x00-\x08\x0B\x0C\x0E-\x1F]/ /g;
                    $decoded =~ tr/\xA0/ /;
                    $decoded =~ s/\x{FEFF}//g;
                    
                    print encode_json({
                        status => 'ok',
                        content => $decoded
                    });
                } else {
                    print encode_json({
                        status => 'error',
                        message => 'No se pudo obtener el changelog'
                    });
                }
            };
            
            if ($@) {
                print encode_json({
                    status => 'error',
                    message => 'Error al obtener el changelog',
                    detail => $@
                });
            }
            exit;
        }
        
        if ($api_action eq 'update') {
            # Manejar solicitudes de update (equivalente a update.cgi)
            # El header JSON ya fue impreso arriba, no imprimir de nuevo
            
            # Solo permitir a root
            my $remote_user = $ENV{REMOTE_USER} || $ENV{HTTP_REMOTE_USER} || '';
            my $is_root_uid = ($> == 0) ? 1 : 0;
            if (($remote_user && $remote_user ne 'root') || (!$remote_user && !$is_root_uid)) {
                print encode_json({ 
                    status => 'error', 
                    message => 'Solo el usuario root puede actualizar el plugin' 
                });
                exit;
            }
            
            my $action = $cgi->param('action') || 'check';
            my $update_url = $cgi->param('url') || 'https://github.com/denialhost/cpanel-multi-log-viewer/releases/latest/download/cpanel-multi-log-viewer.tar.gz';
            
            if ($action eq 'check') {
                # Leer versión actual desde el directorio del plugin
                my $current_version = 'unknown';
                my $version_file = "$FindBin::Bin/VERSION";
                if (-f $version_file) {
                    eval {
                        open my $fh, '<', $version_file or die "No se pudo leer: $!";
                        $current_version = <$fh>;
                        chomp $current_version if $current_version;
                        close $fh;
                    };
                    # Si falla, usar 'unknown' pero no mostrar warning
                    if ($@) {
                        $current_version = 'unknown';
                    }
                }
                
                # Intentar leer versión remota y changelog
                my $remote_version = undef;
                my $changelog = undef;
                my $version_url;
                
                # Si es una URL de GitHub Releases, usar Raw para el changelog
                if ($update_url =~ m|github\.com.*/releases/|) {
                    $version_url = 'https://raw.githubusercontent.com/denialhost/cpanel-multi-log-viewer/main/cpanel-multi-log-viewer-version.txt';
                } else {
                    # Para URLs personalizadas, intentar el patrón antiguo
                    $version_url = $update_url;
                    $version_url =~ s/\.tar\.gz$/-version.txt/;
                }
                
                # Agregar cache busting para evitar caché de GitHub/CDN
                my $cache_buster = time();
                $version_url .= ($version_url =~ /\?/ ? '&' : '?') . "t=$cache_buster";
                
                eval {
                    my $fetch_cmd = "curl -s -k -L --max-time 5 '$version_url' 2>/dev/null || wget -q -O - --no-check-certificate '$version_url' 2>/dev/null";
                    my $remote_content = `$fetch_cmd`;
                    if ($remote_content) {
                        my $decoded = eval { decode('UTF-8', $remote_content) };
                        if ($@) {
                            $decoded = eval { decode('ISO-8859-1', $remote_content) };
                        }
                        $decoded = $decoded // $remote_content;
                        $decoded =~ s/\r\n/\n/g;
                        $decoded =~ s/\r/\n/g;

                        # Limpiar doble codificación caracter a caracter
                        my @sanitized;
                        for my $line (split /\n/, $decoded) {
                            $line =~ s/[\x00-\x08\x0B\x0C\x0E-\x1F]/ /g;
                            $line =~ tr/\xA0/ /;
                            $line =~ s/\xAF\xC2\xBF/ó/g;
                            $line =~ s/\xAF\xC2\xA1/á/g;
                            $line =~ s/\xAF\xC2\xA9/é/g;
                            $line =~ s/\xAF\xC2\xAD/í/g;
                            $line =~ s/\xAF\xC2\xBA/ú/g;
                            $line =~ s/\xAF\xC3\xB1/ñ/g;
                            $line =~ s/\xC3\xB3/ó/g;
                            $line =~ s/\xC3\xA1/á/g;
                            $line =~ s/\xC3\xA9/é/g;
                            $line =~ s/\xC3\xAD/í/g;
                            $line =~ s/\xC3\xBA/ú/g;
                            $line =~ s/\xC3\xB1/ñ/g;
                            $line =~ s/\x{FEFF}//g;
                            $line =~ tr/áéíóúñÁÉÍÓÚÑ/aeiounAEIOUN/;
                            push @sanitized, $line;
                        }
                        $decoded = join "\n", @sanitized;

                        if ($decoded =~ /^(\d+\.\d+(?:\.\d+)?)/m) {
                            $remote_version = $1;
                            $changelog = $decoded;
                            $changelog =~ s/^$remote_version\s*\n?//;
                            $changelog =~ s/^\s+|\s+$//g;
                        }
                    }
                };
                
                # Comparar versiones (simple comparación numérica)
                my $has_update = 0;
                if (!$remote_version) {
                    print encode_json({
                        status => 'error',
                        message => 'No se pudo extraer la versión remota del changelog',
                        detail  => 'El archivo remoto parece vacío o con formato inesperado.'
                    });
                    exit;
                }
                
                if ($remote_version && $current_version ne 'unknown') {
                    # Comparar versiones (ej: 1.0 vs 1.1)
                    my @current = split(/\./, $current_version);
                    my @remote = split(/\./, $remote_version);
                    for my $i (0..$#remote) {
                        my $r = $remote[$i] || 0;
                        my $c = $current[$i] || 0;
                        if ($r > $c) {
                            $has_update = 1;
                            last;
                        } elsif ($r < $c) {
                            last;
                        }
                    }
                }
                
                print encode_json({ 
                    status => 'ok', 
                    current_version => $current_version,
                    remote_version => $remote_version,
                    has_update => $has_update ? JSON::PP::true : JSON::PP::false,
                    changelog => $changelog,
                    update_url => $update_url
                });
                exit;
            }
            
            if ($action eq 'update') {
                if (_install_process_running()) {
                    print encode_json({
                        status => 'error',
                        message => 'Ya hay un proceso de instalación ejecutándose. Espere a que termine o deténgalo manualmente.'
                    });
                    exit;
                }
                
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
                my $lock_created = 0;
                eval {
                    open my $lock_fh, '>', $lock_file or die "No se pudo crear lock file: $!";
                    print $lock_fh $$ . "\n" . time() . "\n";
                    close $lock_fh;
                    $lock_created = 1;
                };
                if ($@ || !$lock_created) {
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error al crear lock file',
                        detail => $@ || 'No se pudo crear el archivo de lock'
                    });
                    exit;
                }
                
                # Asegurar que el lock se elimine al salir (incluso por error)
                eval {
                    require File::Temp;
                    require File::Copy;
                    File::Temp->import(qw(tempdir));
                    File::Copy->import(qw(copy));
                };
                if ($@) {
                    unlink $lock_file if -f $lock_file;
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error al cargar módulos necesarios',
                        detail => $@ 
                    });
                    exit;
                }
                
                my $temp_dir;
                eval {
                    $temp_dir = tempdir(CLEANUP => 1);
                };
                if ($@ || !$temp_dir) {
                    unlink $lock_file if -f $lock_file;
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error al crear directorio temporal',
                        detail => $@ || 'No se pudo crear el directorio temporal'
                    });
                    exit;
                }
                
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
                        my $dh;
                        if (opendir $dh, $temp_dir) {
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
                        } else {
                            $debug_info .= "Error al abrir $temp_dir: $!\n";
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
                    eval {
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
                    };
                    # Si falla, continuar (el install.sh puede estar bien)
                }
                
                # Verificar que install.sh existe y es ejecutable
                if (!-f "$plugin_dir/install.sh") {
                    # Header JSON ya fue impreso arriba
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
                    # Header JSON ya fue impreso arriba
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
                    # Header JSON ya fue impreso arriba
                    print encode_json({ 
                        status => 'error', 
                        message => 'El proceso de instalación excedió el tiempo límite (90 segundos)',
                        detail => 'El script de instalación tomó demasiado tiempo. Esto puede indicar un problema o un bucle infinito. Intente actualizar manualmente desde la línea de comandos.'
                    });
                    exit;
                }
                
                # Si el proceso fue terminado por límite de recursos (143 = SIGTERM, 137 = SIGKILL)
                if ($install_exit == 137 || $install_exit == 143) {
                    # Header JSON ya fue impreso arriba
                    print encode_json({ 
                        status => 'error', 
                        message => 'El proceso de instalación fue terminado por límite de recursos',
                        detail => 'El script de instalación consumió demasiados recursos del sistema. Intente actualizar manualmente desde la línea de comandos.'
                    });
                    exit;
                }
                
                # Guardar versión (usar timestamp como versión)
                # No hacer nada si falla (no es crítico)
                eval {
                    my $version_file = "$FindBin::Bin/.version";
                    open my $fh, '>', $version_file or die "No se pudo escribir: $!";
                    print $fh time() . "\n";
                    close $fh;
                };
                # Ignorar errores (no crítico)
                
                # Decodificar y limpiar la salida de install.sh (preservar UTF-8)
                # Normalizar saltos de línea
                $install_output =~ s/\r\n/\n/g;
                $install_output =~ s/\r/\n/g;
                
                # Intentar decodificar como UTF-8 (sin flags para evitar problemas)
                eval {
                    $install_output = encode('UTF-8', $install_output);
                };
                # Si falla, simplemente usar la salida tal cual (ya está en bytes)
                
                # Limitar tamaño de salida (máximo 50KB para evitar problemas)
                if (length($install_output) > 50000) {
                    $install_output = substr($install_output, 0, 50000) . "\n... (salida truncada por tamaño)";
                }
                
                if ($install_exit != 0) {
                    # Decodificar también el debug_info
                    my $decoded_debug = $final_debug;
                    eval {
                        $decoded_debug = encode('UTF-8', $final_debug);
                    };
                    # Si falla, usar el debug tal cual
                    
                    my $detail = $decoded_debug . "\n--- Salida del script ---\n" . $install_output;
                    
                    # Limitar tamaño total del detalle (máximo 10KB)
                    if (length($detail) > 10000) {
                        $detail = substr($detail, 0, 10000) . "\n... (detalle truncado por tamaño)";
                    }
                    
                    # Header JSON ya fue impreso arriba
                    print encode_json({ 
                        status => 'error', 
                        message => 'Error al ejecutar el script de instalación',
                        detail => $detail,
                        exit_code => $install_exit,
                        debug => $decoded_debug
                    });
                    exit;
                }
                
                # Para respuesta exitosa, limitar salida a 5KB (similar a CSF)
                my $output = $install_output;
                if (length($output) > 5000) {
                    $output = substr($output, 0, 5000) . "\n... (salida truncada)";
                }
                
                # Eliminar lock file al finalizar (éxito)
                unlink $lock_file if -f $lock_file;
                
                # Header JSON ya fue impreso arriba
                print encode_json({ 
                    status => 'ok', 
                    message => 'Plugin actualizado correctamente. Nota: Los servicios no se reiniciaron automáticamente. Si el plugin no aparece, ejecute: /scripts/restartsrv_cpsrvd',
                    output => $output 
                });
                exit;
            }
            
            # Header JSON ya fue impreso arriba
            print encode_json({ status => 'error', message => 'Acción no soportada' });
            exit;
        }
    };
    
    if ($@) {
        my $err = $@ || 'Error interno del servidor';
        my $printed = eval {
            print encode_json({
                status  => 'error',
                message => 'Error al procesar la solicitud API',
                detail  => "$err",
            });
            1;
        };
        if (!$printed) {
            print '{"status":"error","message":"Error al procesar la solicitud API","detail":"Error al codificar JSON"}' . "\n";
        }
        exit 1;
    }
    exit 0;
}

sub handle_download {
    my ($download_id) = @_;
    unless (defined $download_id && length $download_id) {
        print "Status: 400 Bad Request\n";
        print "Content-type: text/plain; charset=utf-8\n\nParámetro de descarga inválido.\n";
        return;
    }

    my $remote_user = $ENV{REMOTE_USER} || $ENV{HTTP_REMOTE_USER} || '';
    if ($remote_user ne 'root') {
        print "Status: 403 Forbidden\n";
        print "Content-type: text/plain; charset=utf-8\n\nSolo el usuario root puede descargar logs desde este módulo.\n";
        return;
    }

    my $config_path = "$FindBin::Bin/config/log_sources.json";
    my $reader = eval { LogReader->new( config_path => $config_path ) };
    if ($@ || !$reader) {
        my $error = $@ || 'No se pudo inicializar LogReader';
        $error =~ s/\s+$//;
        print "Status: 500 Internal Server Error\n";
        print "Content-type: text/plain; charset=utf-8\n\nError al preparar la descarga: $error\n";
        return;
    }

    my $entry = $reader->get_log_entry($download_id);
    unless ($entry && $entry->{path}) {
        print "Status: 404 Not Found\n";
        print "Content-type: text/plain; charset=utf-8\n\nNo se encontró el log solicitado.\n";
        return;
    }

    my $path = $entry->{path};
    unless (-e $path) {
        print "Status: 404 Not Found\n";
        print "Content-type: text/plain; charset=utf-8\n\nEl archivo de log ya no existe.\n";
        return;
    }

    unless (-r $path) {
        print "Status: 403 Forbidden\n";
        print "Content-type: text/plain; charset=utf-8\n\nNo hay permisos para leer este log.\n";
        return;
    }

    open my $fh, '<', $path or do {
        print "Status: 500 Internal Server Error\n";
        print "Content-type: text/plain; charset=utf-8\n\nNo se pudo abrir el archivo de log para descarga.\n";
        return;
    };
    binmode $fh;

    my $stats = stat($fh);
    my $filename = basename($path) || 'log.txt';
    $filename =~ s/[^A-Za-z0-9._-]+/_/g;

    binmode STDOUT;
    print "Content-type: application/octet-stream\n";
    print "Content-Disposition: attachment; filename=\"$filename\"\n";
    print "Cache-Control: no-cache, no-store, must-revalidate\n";
    print "Pragma: no-cache\n";
    print "Expires: 0\n";
    if ($stats) {
        print "Content-Length: " . $stats->size . "\n";
    }
    print "\n";

    my $buffer;
    while (read $fh, $buffer, 8192) {
        print $buffer;
    }
    close $fh;
    return 1;
}

# Si no es API, mostrar la interfaz HTML
eval {
    # Usar el objeto CGI ya creado
    
    binmode STDOUT, ':encoding(UTF-8)';

    # Headers para HTML completo (siempre se abre en nueva pestaña)
    print "Content-type: text/html; charset=utf-8\n";
    print "Cache-Control: no-cache, no-store, must-revalidate\n";
    print "Pragma: no-cache\n";
    print "Expires: 0\n\n";

    # Obtener la ruta base del script actual
    my $script_name = $ENV{SCRIPT_NAME} || '/cgi/mlv/mlv.cgi';
    my $base_path = $script_name;
    $base_path =~ s/[^\/]+$//;  # Remover el nombre del archivo, dejar solo el directorio
    $base_path =~ s/\/$//;      # Remover la barra final si existe
    $base_path = $base_path || '/cgi/mlv';
    
    # Leer versión actual desde el directorio del plugin
    my $current_version = 'unknown';
    my $version_file = "$FindBin::Bin/VERSION";
    if (-f $version_file) {
        eval {
            open my $fh, '<', $version_file or die "No se pudo leer: $!";
            $current_version = <$fh>;
            chomp $current_version if $current_version;
            close $fh;
        };
        # Si falla, usar 'unknown' (no crítico)
    }
    
    # Limpiar versión de cualquier carácter problemático (saltos de línea, espacios, etc.)
    $current_version =~ s/[\r\n\s]+//g;
    $current_version = 'unknown' if !$current_version || $current_version eq '';
    
    # Limpiar base_path de cualquier carácter problemático
    $base_path =~ s/\r\n//g;
    $base_path =~ s/\r//g;
 
    # Cache busting: agregar versión a los assets para forzar recarga
    my $cache_buster = $current_version ne 'unknown' ? "?v=$current_version" : '';

    my $lang_attr_html = 'en';
    my $html_title        = 'Multi Log Viewer';
    my $app_name          = 'Multi Log Viewer';
    my $app_credit        = 'DenialHost SPA';
    my $app_subtitle      = 'Inspect cPanel, Apache, Nginx and firewall logs from a single place.';
    my $button_changelog  = 'Changelog';
    my $button_update     = 'Update Plugin';
    my $filter_placeholder = 'Filter by name';
    my $filter_clear_title = 'Clear search';
    my $lines_label       = 'Last lines:';
    my $search_label      = 'Search:';
    my $search_placeholder = 'Expression or text';
    my $search_clear_title = 'Clear search';
    my $case_label        = 'Case sensitive';
    my $button_search     = 'Search';
    my $button_search_all = 'Search all';
    my $button_live       = 'Live';
    my $button_pause      = 'Pause';
    my $tooltip_live_default = 'Auto-refresh every 5 seconds';
    my $tooltip_pause_live = 'Pause auto-refresh';
    my $tooltip_refresh_default = 'Search in log';
    my $tooltip_refresh_compressed = 'Download the compressed file to review it';
    my $compressed_title  = 'Compressed log';
    my $compressed_text   = 'Download the file to review it locally.';
    my $download_text     = 'Download file';
    my $viewer_initial    = 'Select a log to begin.';
    my $changelog_title   = 'Changelog';
    my $changelog_close   = 'Close';
    my $update_title      = 'Update Plugin';
    my $update_status_checking = 'Checking current version...';
    my $update_button_now = 'Update Now';
    my $update_button_cancel = 'Cancel';

    # HTML completo (siempre se abre en nueva pestaña)
    print <<"HTML";
<!DOCTYPE html>
<html lang="$lang_attr_html">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>$html_title</title>
    <link rel="stylesheet" href="$base_path/assets/style.css$cache_buster" />
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
    <meta http-equiv="Pragma" content="no-cache" />
    <meta http-equiv="Expires" content="0" />
  </head>
  <body>
HTML
    
    print <<"HTML";
    <header>
      <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
          <h1>$app_name <span style="font-size: 0.6em; color: #94a3b8; font-weight: normal;">v$current_version</span> - <span style="font-size: 0.6em; color: #94a3b8; font-weight: normal;">$app_credit</span></h1>
          <p>$app_subtitle</p>
        </div>
        <div style="display: flex; gap: 0.5rem; align-items: center;">
          <button id="show-changelog-btn" style="padding: 0.5rem 1rem; background: rgba(148, 163, 184, 0.2); border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 0.5rem; color: #e2e8f0; cursor: pointer; font-size: 0.85rem;">$button_changelog</button>
          <button id="show-update-btn" style="padding: 0.5rem 1.5rem; background: rgba(148, 163, 184, 0.2); border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 0.5rem; color: #e2e8f0; cursor: pointer; font-size: 0.85rem; position: relative;">
            <span id="update-btn-text">$button_update</span>
            <span id="update-badge" style="display: none; margin-left: 0.5rem; background: #ef4444; color: white; border-radius: 50%; width: 8px; height: 8px; vertical-align: middle; animation: pulse 2s infinite;"></span>
          </button>
        </div>
      </div>
    </header>
    <main id="main-content">
      <aside id="logs-list">
        <div class="search">
          <input id="filter-input" type="text" placeholder="$filter_placeholder" />
          <button id="filter-clear-btn" type="button" title="$filter_clear_title">✕</button>
        </div>
        <ul id="logs"></ul>
      </aside>
      <section id="viewer-column">
        <div id="viewer">
          <div class="controls">
            <label for="lines-input">$lines_label</label>
            <input id="lines-input" type="number" min="10" max="2000" value="100" />
            <label for="search-input">$search_label</label>
            <div style="display: flex; gap: 0.3rem; align-items: center; position: relative;">
              <input id="search-input" type="text" placeholder="$search_placeholder" style="flex: 1;" />
              <button id="clear-search-btn" class="secondary" title="$search_clear_title" style="padding: 0.45rem 0.8rem; min-width: 2rem; display: none; position: absolute; right: 0.3rem; background: rgba(239, 68, 68, 0.8); color: white; border: none;">✕</button>
            </div>
            <label class="checkbox">
              <input type="checkbox" id="case-checkbox" /> $case_label
            </label>
            <button id="refresh-btn">$button_search</button>
            <button id="search-all-btn" class="secondary">$button_search_all</button>
            <button id="live-btn" class="secondary" title="$tooltip_live_default">$button_live</button>
            <button id="pause-btn" class="secondary" style="display: none;" title="$tooltip_pause_live">$button_pause</button>
          </div>
          <div id="status"></div>
          <div id="compressed-banner" class="compressed-banner" style="display: none;">
            <div class="compressed-info">
              <strong>$compressed_title</strong>
              <p id="compressed-text" style="margin: 0.15rem 0 0;">$compressed_text</p>
            </div>
            <div class="compressed-actions">
              <button id="download-compressed-btn" type="button" disabled>$download_text</button>
            </div>
          </div>
          <pre id="log-output"><code>$viewer_initial</code></pre>
        </div>
      </section>
    </main>
    <div id="changelog-panel" style="display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0, 0, 0, 0.7); z-index: 10000; align-items: center; justify-content: center; padding: 2rem;">
      <div style="background: #1e293b; border-radius: 0.75rem; padding: 2rem; max-width: 900px; max-height: 80vh; width: 100%; display: flex; flex-direction: column; gap: 1rem; box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <h2 style="margin: 0; color: #e2e8f0;">$changelog_title</h2>
          <button id="close-changelog-btn" style="background: rgba(148, 163, 184, 0.2); border: 1px solid rgba(148, 163, 184, 0.3); border-radius: 0.5rem; color: #e2e8f0; cursor: pointer; padding: 0.5rem 1rem; font-size: 0.85rem;">$changelog_close</button>
        </div>
        <pre id="changelog-content" style="flex: 1; width: 100%; min-height: 60vh; max-height: 60vh; overflow-y: auto; border: none; border-radius: 0.6rem; background: #0f172a; color: #cbd5e1; padding: 1rem; font-family: 'Courier New', monospace; font-size: 0.9rem; line-height: 1.6; white-space: pre-wrap; word-wrap: break-word; margin: 0;">Loading changelog...</pre>
      </div>
    </div>
    <div id="update-panel" style="display: none;">
      <div class="update-content">
        <h2>$update_title</h2>
        <p id="update-status">$update_status_checking</p>
        <div id="update-progress" style="display: none;">
          <div class="progress-bar">
            <div class="progress-fill"></div>
          </div>
          <p id="update-message"></p>
        </div>
        <div class="update-actions">
          <button id="update-btn" class="primary">$update_button_now</button>
          <button id="cancel-update-btn">$update_button_cancel</button>
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
      // Configuración de verificación de actualizaciones
      window.MLV_UPDATE_CHECK_INTERVAL = 30 * 60 * 1000; // 30 minutos en milisegundos
      // Versión actual para cache busting
      window.MLV_VERSION = "$current_version";
      window.MLV_CHANGELOG_URL = "https://raw.githubusercontent.com/denialhost/cpanel-multi-log-viewer/main/cpanel-multi-log-viewer-version.txt";
    </script>
    <script src="$base_path/assets/app.js$cache_buster"></script>
HTML

    # Cerrar HTML completo
    print "  </body>\n</html>\n";
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
