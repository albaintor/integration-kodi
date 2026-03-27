"""
Kodi Setup fields.

:copyright: (c) 2026 by Albaintor
:license: Mozilla Public License Version 2.0, see LICENSE for more details.
"""

from const import KODI_POWEROFF_COMMANDS, KodiObjectType

KODI_ARTWORK_LABELS = [
    {"id": "thumb", "label": {"en": "Thumbnail", "fr": "Standard"}},
    {"id": "fanart", "label": {"en": "Fan art", "fr": "Fan art"}},
    {"id": "poster", "label": {"en": "Poster", "fr": "Poster"}},
    {"id": "landscape", "label": {"en": "Landscape", "fr": "Paysage"}},
    {"id": "keyart", "label": {"en": "Key art", "fr": "Key art"}},
    {"id": "banner", "label": {"en": "Banner", "fr": "Affiche"}},
    {"id": "clearart", "label": {"en": "Clear art", "fr": "Clear art"}},
    {"id": "clearlogo", "label": {"en": "Clear logo", "fr": "Clear logo"}},
    {"id": "discart", "label": {"en": "Disc art", "fr": "Disc art"}},
    {"id": "icon", "label": {"en": "Icon", "fr": "Icône"}},
    {"id": "set.fanart", "label": {"en": "Fanart set", "fr": "Jeu de fanart"}},
    {"id": "set.poster", "label": {"en": "Poster set", "fr": "Jeu de poster"}},
]

KODI_ARTWORK_TVSHOWS_LABELS = [
    {"id": "thumb", "label": {"en": "Thumbnail", "fr": "Standard"}},
    {"id": "season.banner", "label": {"en": "Season banner", "fr": "Affiche de la saison"}},
    {"id": "season.landscape", "label": {"en": "Season landscape", "fr": "Saison en paysage"}},
    {"id": "season.poster", "label": {"en": "Season poster", "fr": "Affiche de la saison"}},
    {"id": "tvshow.banner", "label": {"en": "TV show banner", "fr": "Affiche de la série"}},
    {"id": "tvshow.characterart", "label": {"en": "TV show character art", "fr": "Personnages de la série"}},
    {"id": "tvshow.clearart", "label": {"en": "TV show clear art", "fr": "Affiche sans fond de la série"}},
    {"id": "tvshow.clearlogo", "label": {"en": "TV show clear logo", "fr": "Logo sans fond de la série"}},
    {"id": "tvshow.fanart", "label": {"en": "TV show fan art", "fr": "Fan art de la série"}},
    {"id": "tvshow.landscape", "label": {"en": "TV show landscape", "fr": "Affiche en paysage"}},
    {"id": "tvshow.poster", "label": {"en": "TV show poster", "fr": "Affiche de la série"}},
    {"id": "icon", "label": {"en": "Icon", "fr": "Icône"}},
]

KODI_DEFAULT_ARTWORK = "thumb"
KODI_DEFAULT_TVSHOW_ARTWORK = "tvshow.poster"

KODI_BROWSING_SORT = {
    KodiObjectType.MOVIE: [
        {"id": "title", "label": {"en": "Name", "fr": "Nom"}},
        {"id": "dateadded descending", "label": {"en": "Date added", "fr": "Date de l'ajout"}},
        {"id": "rating descending", "label": {"en": "Rating", "fr": "Notation"}},
        {"id": "year", "label": {"en": "Year", "fr": "Année"}},
    ],
    KodiObjectType.FILE: [
        {"id": "", "label": {"en": "Name", "fr": "Nom"}},
        {"id": "date descending", "label": {"en": "Date", "fr": "Date"}},
        {"id": "file", "label": {"en": "File", "fr": "Fichier"}},
    ],
    KodiObjectType.ALBUM: [
        {"id": "album", "label": {"en": "Album", "fr": "Album"}},
        {"id": "artist", "label": {"en": "Artist", "fr": "Artiste"}},
        {"id": "dateadded descending", "label": {"en": "Date added", "fr": "Date de l'ajout"}},
        {"id": "rating descending", "label": {"en": "Rating", "fr": "Notation"}},
        {"id": "year", "label": {"en": "Year", "fr": "Année"}},
    ],
}

KODI_BROWSING_CATEGORIES = [
    {"id": "", "label": {"en": "Default", "fr": "Par défaut"}},
    {"id": "kodi://videos", "label": {"en": "Videos", "fr": "Vidéos"}},
    {"id": "kodi://videos/all", "label": {"en": "All videos", "fr": "Toutes les vidéos"}},
    {"id": "kodi://videos/current", "label": {"en": "Current videos", "fr": "Vidéos en cours"}},
    {"id": "kodi://videos/recent", "label": {"en": "Recently added videos", "fr": "Vidéos récemment ajoutées"}},
    {"id": "kodi://tvshows", "label": {"en": "TV Shows", "fr": "Séries"}},
    {"id": "kodi://tvshows/all", "label": {"en": "All TV Shows", "fr": "Toutes les séries"}},
    {"id": "kodi://tvshows/current", "label": {"en": "Current TV Shows", "fr": "Séries en cours"}},
    {
        "id": "kodi://tvshows/recent",
        "label": {"en": "Recently added TV Shows episodes", "fr": "Episodes de séries ajoutés récemment"},
    },
    {"id": "kodi://music", "label": {"en": "Music", "fr": "Musique"}},
    {"id": "kodi://music/albums", "label": {"en": "Music albums", "fr": "Albums de musique"}},
    {"id": "kodi://music/playlists", "label": {"en": "Music playlists", "fr": "Listes de musique"}},
    {"id": "kodi://sources", "label": {"en": "Sources", "fr": "Sources"}},
    {"id": "kodi://sources/videos", "label": {"en": "Video sources", "fr": "Sources de vidéos"}},
    {"id": "kodi://sources/music", "label": {"en": "Music sources", "fr": "Sources de musique"}},
    {"id": "kodi://sources/pictures", "label": {"en": "Pictures sources", "fr": "Sources d'images"}},
]

SETUP_FIELDS = [
    {
        "field": {"text": {"value": ""}},
        "id": "username",
        "label": {"en": "Username", "fr": "Utilisateur"},
    },
    {
        "field": {"text": {"value": ""}},
        "id": "password",
        "label": {"en": "Password", "fr": "Mot de passe"},
    },
    {
        "field": {"text": {"value": "9090"}},
        "id": "ws_port",
        "label": {"en": "Websocket port", "fr": "Port websocket"},
    },
    {
        "field": {"text": {"value": "8080"}},
        "id": "port",
        "label": {"en": "HTTP port", "fr": "Port HTTP"},
    },
    {
        "field": {"checkbox": {"value": False}},
        "id": "ssl",
        "label": {"en": "Use SSL", "fr": "Utiliser SSL"},
    },
    {
        "field": {"dropdown": {"value": KODI_DEFAULT_ARTWORK, "items": KODI_ARTWORK_LABELS}},
        "id": "artwork_type",
        "label": {
            "en": "Artwork type to display",
            "fr": "Type d'image média à afficher",
        },
    },
    {
        "field": {"dropdown": {"value": KODI_DEFAULT_TVSHOW_ARTWORK, "items": KODI_ARTWORK_TVSHOWS_LABELS}},
        "id": "artwork_type_tvshows",
        "label": {
            "en": "Artwork type to display for TV Shows",
            "fr": "Type d'image média à afficher pour les séries",
        },
    },
    {
        "field": {
            "dropdown": {
                "value": "",
                "items": KODI_BROWSING_CATEGORIES,
            }
        },
        "id": "browse_media_root",
        "label": {
            "en": "Default browsing media category",
            "fr": "Catégorie de navigation par défaut",
        },
    },
    {
        "field": {
            "dropdown": {
                "value": "title",
                "items": KODI_BROWSING_SORT[KodiObjectType.MOVIE],
            }
        },
        "id": "browsing_video_sort",
        "label": {
            "en": "Sorting method for video browsing",
            "fr": "Méthode de tri pour la navigation vidéo",
        },
    },
    {
        "field": {
            "dropdown": {
                "value": "album",
                "items": KODI_BROWSING_SORT[KodiObjectType.ALBUM],
            }
        },
        "id": "browsing_album_sort",
        "label": {
            "en": "Sorting method for albums browsing",
            "fr": "Méthode de tri pour la navigation des albums",
        },
    },
    {
        "field": {
            "dropdown": {
                "value": "",
                "items": KODI_BROWSING_SORT[KodiObjectType.FILE],
            }
        },
        "id": "browsing_files_sort",
        "label": {
            "en": "Sorting method for files browsing",
            "fr": "Méthode de tri pour la navigation de fichiers",
        },
    },
    {
        "field": {"checkbox": {"value": True}},
        "id": "show_stream_name",
        "label": {
            "en": "Show audio/subtitle track name",
            "fr": "Afficher le nom de la piste audio/sous-titres",
        },
    },
    {
        "field": {"checkbox": {"value": True}},
        "id": "show_stream_language_name",
        "label": {
            "en": "Show language name instead of track name",
            "fr": "Afficher le nom de la langue au lieu du nom de la piste",
        },
    },
    {
        "field": {"checkbox": {"value": True}},
        "id": "media_update_task",
        "label": {"en": "Enable media update task", "fr": "Activer la tâche de mise à jour du média"},
    },
    {
        "field": {"checkbox": {"value": False}},
        "id": "download_artwork",
        "label": {
            "en": "Download artwork instead of transmitting URL to the remote",
            "fr": "Télécharger l'image au lieu de transmettre l'URL à la télécommande",
        },
    },
    {
        "field": {"checkbox": {"value": False}},
        "id": "disable_keyboard_map",
        "label": {
            "en": "Disable keyboard map : check only if some commands fail (eg arrow keys)",
            "fr": "Désactiver les commandes clavier : cocher uniquement si certaines commandes échouent "
            "(ex : commandes de direction)",
        },
    },
    {
        "field": {
            "dropdown": {
                "value": next(iter(KODI_POWEROFF_COMMANDS)),
                "items": [{"id": key, "label": value} for key, value in KODI_POWEROFF_COMMANDS.items()],
            }
        },
        "id": "power_off_command",
        "label": {
            "en": "Power off command",
            "fr": "Commande d'arrêt",
        },
    },
]
