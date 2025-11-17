package LogReader;

use strict;
use warnings;

use File::stat;
use File::Find;
use JSON::PP qw(decode_json);

sub new {
    my ($class, %args) = @_;
    my $self = {
        config_path => $args{config_path},
        _config     => undef,
    };

    die "config_path es obligatorio" unless $self->{config_path};

    bless $self, $class;
    $self->_load_config;
    return $self;
}

sub list_logs {
    my ($self) = @_;

    my @logs;
    my %seen_paths;  # Para evitar duplicados
    
    # Primero agregar logs de la configuración
    for my $entry (@{ $self->{_config}->{logs} || [] }) {
        my $path = $entry->{path};
        $seen_paths{$path} = 1;
        
        my $info = {
            id          => $entry->{id},
            name        => $entry->{name},
            path        => $path,
            default_tail=> $entry->{default_tail} || 100,
            exists      => -e $path ? JSON::PP::true : JSON::PP::false,
            auto_detected => JSON::PP::false,
            priority    => $entry->{priority} || 100,  # Prioridad por defecto: 100 (baja)
            category    => $entry->{category} || 'Other',  # Categoría del log
        };

        my $is_compressed = _is_compressed($path);
        $info->{compressed} = $is_compressed ? JSON::PP::true : JSON::PP::false;
        if ($is_compressed) {
            $info->{priority} = ($info->{priority} || 100) + 200;
        }

        if (-e $path) {
            my $stats = stat($path);
            if ($stats) {
                $info->{size}  = $stats->size;
                $info->{mtime} = $stats->mtime;
            }
        } else {
            # Los logs que no existen tienen prioridad muy baja
            $info->{priority} = 999;
        }

        push @logs, $info;
    }
    
    # Luego agregar logs detectados automáticamente
    my @auto_logs = $self->_detect_logs(\%seen_paths);
    push @logs, @auto_logs;

    # Ordenar logs por prioridad:
    # 1. Existen y tienen prioridad baja (más importantes)
    # 2. Existen y tienen prioridad alta (menos importantes)
    # 3. No existen (al final)
    @logs = sort {
        my $a_exists = $a->{exists} ? 1 : 0;
        my $b_exists = $b->{exists} ? 1 : 0;
        
        # Primero: los que existen vs los que no
        return $b_exists <=> $a_exists if $a_exists != $b_exists;
        
        # Si ambos existen o ambos no existen, ordenar por prioridad
        my $a_priority = $a->{priority} || 100;
        my $b_priority = $b->{priority} || 100;
        
        # Si tienen la misma prioridad, ordenar por tamaño (más grande primero)
        if ($a_priority == $b_priority && $a_exists) {
            my $a_size = $a->{size} || 0;
            my $b_size = $b->{size} || 0;
            return $b_size <=> $a_size;
        }
        
        return $a_priority <=> $b_priority;
    } @logs;

    return \@logs;
}

sub _detect_logs {
    my ($self, $seen_paths) = @_;
    my @detected;
    
    # Patrones de ubicaciones comunes de logs
    my @search_paths = (
        { path => '/usr/local/cpanel/logs', pattern => qr/\.(log|LOG)$/, name_prefix => 'cPanel' },
        { path => '/var/log', pattern => qr/\.(log|LOG)$|^(exim_|maillog|messages|secure|cron|mysqld|php-fpm|clamav|lfd)/, name_prefix => 'System' },
        { path => '/etc/apache2/logs', pattern => qr/\.(log|LOG)$/, name_prefix => 'Apache' },
        { path => '/var/log/apache2', pattern => qr/\.(log|LOG)$/, name_prefix => 'Apache' },
        { path => '/var/log/nginx', pattern => qr/\.(log|LOG)$/, name_prefix => 'Nginx' },
        { path => '/var/log/mysql', pattern => qr/\.(log|LOG)$/, name_prefix => 'MySQL' },
    );
    
    for my $search (@search_paths) {
        next unless -d $search->{path};
        
        my @found_files;
        eval {
            find(sub {
                return unless -f $_;
                return unless $_ =~ $search->{pattern};
                my $full_path = $File::Find::name;
                return if $seen_paths->{$full_path};
                return unless -r $full_path;
                push @found_files, $full_path;
            }, $search->{path});
        };
        
        for my $file_path (@found_files) {
            next if $seen_paths->{$file_path};
            $seen_paths->{$file_path} = 1;
            
            my $name = $self->_generate_log_name($file_path, $search->{name_prefix});
            my $id = $self->_generate_log_id($file_path);
            
            my $info = {
                id            => $id,
                name          => $name,
                path          => $file_path,
                default_tail  => 100,
                exists        => JSON::PP::true,
                auto_detected => JSON::PP::true,
                priority      => 100,  # Prioridad baja para logs auto-detectados
                category      => $self->_detect_category($file_path, $search->{name_prefix}),
            };

            my $is_compressed = _is_compressed($file_path);
            $info->{compressed} = $is_compressed ? JSON::PP::true : JSON::PP::false;
            if ($is_compressed) {
                $info->{priority} = ($info->{priority} || 100) + 200;
            }
            
            my $stats = stat($file_path);
            if ($stats) {
                $info->{size}  = $stats->size;
                $info->{mtime} = $stats->mtime;
            }
            
            push @detected, $info;
        }
    }
    
    return @detected;
}

sub _generate_log_name {
    my ($self, $path, $prefix) = @_;
    my $basename = (split('/', $path))[-1];
    $basename =~ s/\.(log|LOG)$//;
    $basename =~ s/_/ /g;
    $basename =~ s/\b(\w)/\u$1/g;  # Capitalizar primera letra de cada palabra
    
    return "$prefix $basename" if $prefix;
    return $basename;
}

sub _generate_log_id {
    my ($self, $path) = @_;
    my $id = $path;
    $id =~ s/[^a-zA-Z0-9]/_/g;
    $id =~ s/_+/_/g;
    $id =~ s/^_|_$//g;
    $id = lc($id);
    return "auto_$id";
}

sub _detect_category {
    my ($self, $path, $prefix) = @_;
    
    # Detectar categoría basada en la ruta
    if ($path =~ m{/cpanel/|/whm/}) {
        return 'cPanel';
    } elsif ($path =~ m{/apache|/httpd}) {
        return 'Web Server';
    } elsif ($path =~ m{/nginx}) {
        return 'Web Server';
    } elsif ($path =~ m{/exim|/mail|/postfix|/sendmail}) {
        return 'Mail';
    } elsif ($path =~ m{/mysql|/mariadb}) {
        return 'Database';
    } elsif ($path =~ m{/lfd|/csf|/firewall|/clamav|/fail2ban}) {
        return 'Security';
    } elsif ($path =~ m{/var/log/(messages|secure|cron|syslog)}) {
        return 'System';
    } elsif ($prefix) {
        # Usar el prefijo como categoría si está disponible
        return $prefix;
    }
    
    return 'Other';
}

sub tail_log {
    my ($self, %args) = @_;

    my $id            = $args{id}            or return _error('Falta el parámetro id');
    my $lines         = $args{lines}         || 100;
    my $search        = defined $args{search} ? $args{search} : '';
    my $case_sensitive= $args{case_sensitive} ? 1 : 0;

    my $entry = $self->_log_by_id($id)
      or return _error('Log no definido en la configuración');

    my $path = $entry->{path};
    return _error('El archivo de log no existe') unless -e $path;
    return _error('No se tiene permiso para leer el log') unless -r $path;

    if (_is_compressed($path)) {
        return {
            status      => 'ok',
            compressed  => JSON::PP::true,
            message     => 'Este log está comprimido. Descárgalo para revisarlo sin descomprimir en el navegador.',
            meta        => _log_metadata($path),
            lines       => [],
        };
    }

    my @data;
    
    # Si hay un término de búsqueda, buscar en TODO el archivo
    # Si no hay búsqueda, solo mostrar las últimas N líneas
    if (length $search) {
        # Buscar en todo el archivo cuando hay un término de búsqueda
        @data = _read_file($path);
        
        # Aplicar el filtro de búsqueda
        my $regex;
        eval {
            $regex = $case_sensitive ? qr/$search/ : qr/$search/i;
        };
        if ($@) {
            return _error('Expresión de búsqueda inválida');
        }
        @data = grep { $_ =~ $regex } @data;
        
        # Limitar el número de resultados mostrados (pero buscar en todo el archivo)
        my $max_results = $lines || 2000;
        if (@data > $max_results) {
            @data = @data[-$max_results..$#data];  # Mostrar los últimos N resultados
        }
    } else {
        # Sin búsqueda: solo mostrar las últimas N líneas
        my $actual_lines = $lines || $entry->{default_tail} || 200;
        @data = _read_tail($path, $actual_lines);
    }

    return {
        status => 'ok',
        meta   => _log_metadata($path),
        lines  => \@data,
    };
}

sub search_all_logs {
    my ($self, %args) = @_;

    my $search         = defined $args{search} ? $args{search} : '';
    my $case_sensitive = $args{case_sensitive} ? 1 : 0;
    my $lines          = $args{lines} && $args{lines} > 0 ? $args{lines} : 500;

    return _error('El parámetro search es obligatorio') unless length $search;

    my $regex;
    eval {
        $regex = $case_sensitive ? qr/$search/ : qr/$search/i;
    };
    if ($@) {
        return _error('Expresión de búsqueda inválida');
    }

    my @matches;
    my $processed = 0;
    
    # Obtener todos los logs (configurados + auto-detectados)
    my %seen_paths;
    my @all_logs = @{ $self->{_config}->{logs} || [] };
    for my $entry (@all_logs) {
        $seen_paths{$entry->{path}} = 1;
    }
    push @all_logs, $self->_detect_logs(\%seen_paths);

    for my $entry (@all_logs) {
        my $path = $entry->{path};
        next unless -e $path && -r $path;

        next if _is_compressed($path);

        my @content = _read_file($path);
        my @hits    = grep { $_ =~ $regex } @content;
        
        # Limitar el número de resultados mostrados por log
        if (@hits > $lines) {
            @hits = @hits[-$lines..$#hits];  # Mostrar los últimos N resultados
        }
        
        next unless @hits;

        push @matches, {
            id      => $entry->{id},
            name    => $entry->{name},
            path    => $path,
            matches => \@hits,
        };

        $processed++;
    }

    return {
        status    => 'ok',
        processed => $processed,
        matches   => \@matches,
    };
}

sub _log_metadata {
    my ($path) = @_;
    my $stats = stat($path);
    return unless $stats;

    return {
        path  => $path,
        size  => $stats->size,
        mtime => $stats->mtime,
    };
}

sub _read_file {
    my ($path) = @_;
    
    open my $fh, '<', $path or return ();
    binmode $fh;
    
    my @lines;
    while (my $line = <$fh>) {
        chomp $line;
        push @lines, $line;
    }
    
    close $fh;
    return @lines;
}

sub _read_tail {
    my ($path, $lines) = @_;

    $lines = 200 unless $lines && $lines > 0;

    open my $fh, '<', $path or return ();
    binmode $fh;

    my $max_bytes = 2 * 1024 * 1024; # 2 MB
    my $size = -s $fh;
    my $seek = $size > $max_bytes ? $size - $max_bytes : 0;

    seek $fh, $seek, 0;
    <$fh> if $seek; # descartar línea parcial

    my @buffer;
    while (my $line = <$fh>) {
        chomp $line;
        push @buffer, $line;
        shift @buffer while @buffer > $lines;
    }

    close $fh;
    return @buffer;
}

sub _log_by_id {
    my ($self, $id) = @_;
    
    # Buscar primero en la configuración
    for my $entry (@{ $self->{_config}->{logs} || [] }) {
        return $entry if $entry->{id} eq $id;
    }
    
    # Si no se encuentra, buscar en logs auto-detectados
    my %seen_paths;
    for my $entry (@{ $self->{_config}->{logs} || [] }) {
        $seen_paths{$entry->{path}} = 1;
    }
    
    my @auto_logs = $self->_detect_logs(\%seen_paths);
    for my $entry (@auto_logs) {
        return $entry if $entry->{id} eq $id;
    }
    
    return;
}

sub get_log_entry {
    my ($self, $id) = @_;

    my $entry = $self->_log_by_id($id);
    return unless $entry;

    my $path = $entry->{path};
    my $info = { %{$entry} };
    $info->{path}       = $path;
    $info->{exists}     = -e $path ? JSON::PP::true : JSON::PP::false;
    $info->{readable}   = -r $path ? JSON::PP::true : JSON::PP::false;
    $info->{compressed} = _is_compressed($path) ? JSON::PP::true : JSON::PP::false;

    my $stats = (-e $path) ? stat($path) : undef;
    if ($stats) {
        $info->{size}  = $stats->size;
        $info->{mtime} = $stats->mtime;
    }

    return $info;
}

sub _load_config {
    my ($self) = @_;
    my $path = $self->{config_path};

    open my $fh, '<', $path or die "No se pudo abrir $path: $!";
    local $/;
    my $json = <$fh>;
    close $fh;

    my $config = decode_json($json);
    die "El archivo de configuración no contiene un array de logs" unless ref $config->{logs} eq 'ARRAY';

    $self->{_config} = $config;
}

sub _error {
    my ($message) = @_;
    return { status => 'error', message => $message };
}

sub _is_compressed {
    my ($path) = @_;
    return 0 unless defined $path;
    return $path =~ /\.(?:gz|bz2|xz|zip|lz4|lz|tgz|zst)(?:\.[\d]+)?$/i;
}

1;

