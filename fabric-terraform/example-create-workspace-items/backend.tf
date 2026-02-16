terraform {
  backend "azurerm" {
    resource_group_name   = "Resourcegroup Name here"
    storage_account_name  = "storageaccountnamehere"
    container_name        = "fabricstate"
    key                   = "terraform.fabricstate"
  }
}
