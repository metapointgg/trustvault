@description('Azure region')
param location string = resourceGroup().location

@description('Name prefix for TrustVault resources')
param namePrefix string = 'trustvault'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${namePrefix}storage'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource sourceImports 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storage.name}/default/source-imports'
}

resource fitsContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storage.name}/default/fits-containers'
}

resource derivedReports 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storage.name}/default/derived-reports'
}

// Container Apps, Azure Database for PostgreSQL, Service Bus, Key Vault,
// Managed Identity, Log Analytics and Private Endpoints are defined as
// controlled-deployment module boundaries and should be completed for each
// client tenant/subscription.
