import os
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
import threading
import io
import sys
import configparser
import logging
import traceback

from spotify_playlist_to_m3u8 import (SpotifyClient, format_track_info, search_songs_from_track_list,gen_m3u8_playlist)

def get_resource_path(relative_path):
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)

class RedirectText:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = io.StringIO()
        
    def write(self, string):
        self.buffer.write(string)
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)  # Auto-scroll
        self.text_widget.update_idletasks()
        
    def flush(self):
        pass

class SpotifyPlaylistConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Conversor de Playlists de Spotify")
        self.root.geometry("800x600")
        self.root.minsize(600, 500)

        icon = tk.PhotoImage(file=get_resource_path("icon.png"))
        self.root.iconphoto(True, icon)
 
        # Cargar configuración si existe
        self.config_file = "config.ini"
        self.config = configparser.ConfigParser()
        self.load_config()
        
        # Variables
        self.spotify_client_id = tk.StringVar(value=self.config.get("Spotify", "client_id", fallback=""))
        self.spotify_client_secret = tk.StringVar(value=self.config.get("Spotify", "client_secret", fallback=""))
        self.music_dir = tk.StringVar(value=self.config.get("Paths", "music_directory", fallback=""))
        self.output_dir = tk.StringVar(value=self.config.get("Paths", "output_directory", fallback=""))
        self.playlist_url = tk.StringVar()
        
        # Crear interfaz
        self.create_widgets()
        
        # Configurar logging
        self.configure_logging()
        
        
    def load_config(self):
        """Cargar configuración desde el archivo config.ini si existe"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            # Crear estructura de configuración por defecto
            self.config["Spotify"] = {
                "client_id": "",
                "client_secret": ""
            }
            self.config["Paths"] = {
                "music_directory": "",
                "output_directory": ""
            }
    
    def save_config(self):
        self.config["Spotify"]["client_id"] = self.spotify_client_id.get()
        self.config["Spotify"]["client_secret"] = self.spotify_client_secret.get()
        self.config["Paths"]["music_directory"] = self.music_dir.get()
        self.config["Paths"]["output_directory"] = self.output_dir.get()
        
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)
        
        self.log_info("Configuración guardada")
        
    def create_widgets(self):
        # Crear el notebook para las pestañas y guardarlo como atributo de la clase
        self.tabControl = ttk.Notebook(self.root)
        
        self.tab_converter = ttk.Frame(self.tabControl)
        self.tabControl.add(self.tab_converter, text="Conversor")
        
        self.tab_settings = ttk.Frame(self.tabControl)
        self.tabControl.add(self.tab_settings, text="Configuración")
        
        self.tabControl.pack(expand=1, fill="both", padx=10, pady=10)
        
        self.setup_converter_tab(self.tab_converter)
        self.setup_settings_tab(self.tab_settings)

        
    def setup_converter_tab(self, parent):
        self.frame_url = ttk.LabelFrame(parent, text="Playlist")
        self.frame_url.pack(fill="x", padx=10, pady=(10, 5), ipady=5)
        
        ttk.Label(self.frame_url, text="URL de Spotify:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(self.frame_url, textvariable=self.playlist_url, width=60).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.frame_url.columnconfigure(1, weight=1)
        
        # Botón para iniciar la conversión - guardarlo como atributo para poder accederlo fácilmente
        self.convert_button = ttk.Button(self.frame_url, text="Convertir", command=self.start_conversion)
        self.convert_button.grid(row=0, column=2, padx=5, pady=5)
        
        # Área de logs
        frame_log = ttk.LabelFrame(parent, text="Logs")
        frame_log.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Configuramos el widget de texto para los logs
        self.log_text = scrolledtext.ScrolledText(frame_log, wrap=tk.WORD, height=15)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)
    
        
    def setup_settings_tab(self, parent):
        """Configurar la pestaña de configuración"""
        frame_spotify = ttk.LabelFrame(parent, text="Credenciales de Spotify API")
        frame_spotify.pack(fill="x", padx=10, pady=(10, 5), ipady=5)
        
        # Cliente ID
        ttk.Label(frame_spotify, text="Client ID:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_spotify, textvariable=self.spotify_client_id, width=50).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # Cliente Secret
        ttk.Label(frame_spotify, text="Client Secret:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_spotify, textvariable=self.spotify_client_secret, width=50, show="*").grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        # Información adicional
        info_text = "Nota: Para obtener las credenciales de Spotify API, regístrate en https://developer.spotify.com/dashboard/"
        ttk.Label(frame_spotify, text=info_text, wraplength=500).grid(row=2, column=1, pady=5)
        
        # Frame para directorios
        frame_dirs = ttk.LabelFrame(parent, text="Directorios")
        frame_dirs.pack(fill="x", padx=10, pady=5, ipady=5)
        
        # Directorio de música
        ttk.Label(frame_dirs, text="Biblioteca de música:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_dirs, textvariable=self.music_dir, width=50).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame_dirs, text="Buscar", command=lambda: self.browse_directory(self.music_dir)).grid(row=0, column=2, padx=5, pady=5)
        
        # Directorio de salida
        ttk.Label(frame_dirs, text="Directorio de salida:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        ttk.Entry(frame_dirs, textvariable=self.output_dir, width=50).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(frame_dirs, text="Buscar", command=lambda: self.browse_directory(self.output_dir)).grid(row=1, column=2, padx=5, pady=5)
        
        # Botón para guardar configuración
        self.save_button = ttk.Button(parent, text="Guardar Configuración", command=self.save_config)
        self.save_button.pack(side=tk.BOTTOM, pady=10)

        
    def browse_directory(self, string_var):
        directory = filedialog.askdirectory(initialdir=string_var.get())
        if directory:
            string_var.set(directory)
    
    def configure_logging(self):
        self.logger = logging.getLogger("SpotifyConverterGUI")
        self.logger.setLevel(logging.INFO)
        
        # Redirect handler que envía los logs al widget de texto
        text_handler = logging.StreamHandler(RedirectText(self.log_text))
        text_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
        
        # Añadir el handler al logger
        self.logger.addHandler(text_handler)
        
        #redirigir stdout y stderr al widget
        sys.stdout = RedirectText(self.log_text)
        sys.stderr = RedirectText(self.log_text)
    
    def log_info(self, message):
        self.logger.info(message)
        
    def log_error(self, message):
        self.logger.error(message)

    
    def validate_inputs(self):
        if not self.spotify_client_id.get().strip():
            self.log_error("Error: Client ID de Spotify no configurado")
            return False
            
        if not self.spotify_client_secret.get().strip():
            self.log_error("Error: Client Secret de Spotify no configurado")
            return False
            
        if not self.music_dir.get().strip():
            self.log_error("Error: Directorio de música no configurado")
            return False
            
        if not self.output_dir.get().strip():
            self.log_error("Error: Directorio de salida no configurado")
            return False
            
        if not self.playlist_url.get().strip():
            self.log_error("Error: URL de playlist no proporcionada")
            return False
            
        # Verificar que los directorios existan
        if not os.path.isdir(self.music_dir.get()):
            self.log_error(f"Error: El directorio de música no existe: {self.music_dir.get()}")
            return False
            
        if not os.path.isdir(self.output_dir.get()):
            # Intentar crear el directorio de salida si no existe
            try:
                os.makedirs(self.output_dir.get())
                self.log_info(f"Directorio de salida creado: {self.output_dir.get()}")
            except Exception as e:
                self.log_error(f"Error al crear el directorio de salida: {str(e)}")
                return False
                
        return True
    
    def start_conversion(self):
        if not self.validate_inputs():
            return
            
        # Deshabilitar el botón de convertir directamente
        self.convert_button.configure(state="disabled")
                
        threading.Thread(target=self.convert_playlist, daemon=True).start()
    
    def convert_playlist(self):
        try:
            self.log_info("Iniciando conversión de playlist...")
            self.log_info(f"URL: {self.playlist_url.get()}")
            
            # Inicializar cliente de Spotify
            spotify = SpotifyClient(self.spotify_client_id.get(), self.spotify_client_secret.get())
            
            # Obtener ID y nombre de la playlist
            playlist_id = spotify.extract_playlist_id(self.playlist_url.get())
            playlist_name = spotify.get_playlist_name(playlist_id)
            
            self.log_info(f"Procesando playlist: {playlist_name} (ID: {playlist_id})")
            
            playlist_tracks = spotify.get_playlist_tracks(playlist_id)
            self.log_info(f"Encontradas {len(playlist_tracks)} pistas en la playlist")
            
            all_tracks = [format_track_info(track) for track in playlist_tracks if 'track' in track and track['track']]
            all_tracks = [track for track in all_tracks if track]
            
            self.log_info("Buscando coincidencias en la biblioteca local...")
            found_songs, not_found_songs = search_songs_from_track_list(self.music_dir.get(), all_tracks)
            
            self.log_info("Generando archivo M3U8...")
            playlist_path = gen_m3u8_playlist(
                self.music_dir.get(),
                found_songs,
                not_found_songs,
                self.output_dir.get(),
                playlist_name
            )
            
            found_percent = (len(found_songs) / len(all_tracks)) * 100 if all_tracks else 0
            self.log_info(f"Procesamiento de playlist completado: {len(found_songs)}/{len(all_tracks)} pistas encontradas ({found_percent:.1f}%)")
            self.log_info(f"Playlist guardada en: {playlist_path}")
            
        except Exception as e:
            self.log_error(f"Error al procesar la playlist: {str(e)}")
            self.log_error(traceback.format_exc())
        finally:
            # Usar root.after para habilitar el botón en el hilo principal
            self.root.after(0, lambda: self.convert_button.configure(state="normal"))
    
if __name__ == "__main__":
    root = tk.Tk()
    app = SpotifyPlaylistConverterGUI(root)
    root.mainloop()