# 1) Install Package
%pip install --upgrade semantic-link-sempy -q

# 2) Imports
import sempy.fabric as fabric
import pandas as pd
from IPython.display import display, HTML

def summarize_workspace_items(full_display: bool = True):
    """
    Erstellt einen DataFrame mit allen Items (Lakehouse, Warehouse, etc.) in allen Workspaces
    und zeigt ihn als vollständige Tabelle an.
    
    Parameter:
        full_display (bool): Wenn True, zeigt alle Zeilen und Spalten scrollbar an.
    Rückgabe:
        df (pd.DataFrame): DataFrame mit allen Items.
    """
    
    # Workspaces abrufen
    workspaces = fabric.list_workspaces()
    workspaces = workspaces.query("Type == 'Workspace'")  # nur normale Workspaces
    
    rows = []
    
    for ws_id, ws_name in zip(workspaces["Id"], workspaces["Name"]):
        items = fabric.list_items(workspace=ws_id)
        if items.empty:
            continue
        
        # Item-Typen automatisch bestimmen
        for item_type in items["Type"].unique():
            subset = items[items["Type"] == item_type].copy()
            if subset.empty:
                continue
            
            subset["workspace_name"] = ws_name
            subset["Item Type"] = item_type
            subset["item_id"] = subset["Id"]
            subset["item_name"] = subset.get("Name", subset.get("displayName", subset.get("Display Name")))
            
            rows.append(subset[["item_id","item_name","workspace_name","Item Type"]])
    
    # Zusammenführen
    if rows:
        df = pd.concat(rows, ignore_index=True)
    else:
        df = pd.DataFrame(columns=["item_id","item_name","workspace_name","Item Type"])
    
    # Sortieren
    df = df.sort_values(["workspace_name","item_name"]).reset_index(drop=True)
    
    # Vollständige Tabelle anzeigen
    if full_display:
        pd.set_option("display.max_rows", None)
        pd.set_option("display.max_columns", None)
        pd.set_option("display.width", 200)
        display(HTML(df.to_html(max_rows=None, max_cols=None)))
    
    return df

# Funktion ausführen und DataFrame erhalten
df_items = summarize_workspace_items()
