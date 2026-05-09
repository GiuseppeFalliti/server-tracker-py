"""
Lookup degli AVL ID Teltonika.

Questo modulo carica il file JSON con la descrizione degli AVL ID e
fornisce un metodo semplice per recuperare il significato di un ID.
"""

import json

from logger import app_logger


class avlIdMatcher:
    """Espone una piccola utility per risolvere un AVL ID in metadati leggibili."""

    def __init__(self):
        self.avl_data = self.loadData()

    def loadData(self):
        # Il file viene letto una sola volta all'avvio dell'oggetto.
        with open('avlIds.json') as f:
            data = json.load(f)
        return data

    def getAvlInfo(self, id):
        # Restituisce il record associato all'ID richiesto.
        try:
            data = self.avl_data[id]
            return data
        except Exception:
            # In caso di ID assente, scrive un evento e segnala il fallback.
            app_logger.log_system_event(
                level="WARNING",
                event_type="avl_id_not_found",
                message="AVL ID non presente nel catalogo.",
                component="avl_matcher",
                details={"avl_id": id},
            )
            return -1


if __name__ == "__main__":
    # Esempio di consultazione della tabella degli AVL ID.
    data = avlIdMatcher()
    app_logger.log_system_event(
        level="INFO",
        event_type="avl_matcher_sample_lookup",
        message="Lookup di esempio su AVL IDs.",
        component="avl_matcher",
        details={
            "id_4": data.getAvlInfo("4")["name"],
            "id_1": data.getAvlInfo("1"),
        },
    )
