data "fabric_capacity" "capacity" {
  display_name = var.capacity_name
}

## Create Workspace ##
resource "fabric_workspace" "workspace_name" {
    display_name = var.workspace_name
    capacity_id  = data.fabric_capacity.capacity.id
  
}

## Create Fabric Warehouse ##
resource "fabric_warehouse" "warehouse_name" {
    display_name = var.warehouse_name
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Lakehouse ##
resource "fabric_lakehouse" "lakehouse_name" {
    display_name = var.lakehouse_name_bronze
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Lakehouse ##
resource "fabric_lakehouse" "lakehouse_silver" {
    display_name = var.lakehouse_name_silver
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Lakehouse ##
resource "fabric_lakehouse" "lakehouse_gold" {
    display_name = var.lakehouse_name_gold
    workspace_id = fabric_workspace.workspace_name.id
}


## Create Fabric Folder ##
resource "fabric_folder" "folder_for_notebooks" {
    display_name = var.notebook_folder_name
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Folder ##
resource "fabric_folder" "folder_for_pipelines" {
    display_name = var.pipelines_folder_name
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Folder ##
resource "fabric_folder" "folder_for_reports" {
    display_name = var.power_bi_reports_folder_name
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Folder ##
resource "fabric_folder" "folder_for_user_data_functions" {
    display_name = var.user_data_functions_folder_name
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Folder ##
resource "fabric_folder" "folder_for_variables" {
    display_name = var.variables_folder_name
    workspace_id = fabric_workspace.workspace_name.id
}

## Create Fabric Notebook ##
resource "fabric_notebook" "notebook_1" {
  display_name = var.notebook_1_name
  workspace_id = fabric_workspace.workspace_name.id
  definition_update_enabled = true
  format = "ipynb"
  definition = {
  "notebook-content.ipynb" = {
    source = "Fabric/Notebooks/NB Get Azure Resources Tenant 1.ipynb"
  }
}
}
