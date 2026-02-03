output "workspace_name" {
  description = "Workspace Name"
  value       = fabric_workspace.workspace_name.display_name
}

output "workspace_id" {
  description = "Workspace ID"
  value       = fabric_workspace.workspace_name.id
}

output "lakehouse_name" {
  description = "Lakehouse Name"
  value       = fabric_lakehouse.lakehouse_name.display_name
}

output "warehouse_name" {
  description = "Warehouse Name"
  value       = fabric_warehouse.warehouse_name.display_name
}

