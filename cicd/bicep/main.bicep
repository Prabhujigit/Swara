targetScope = 'subscription'

param cognitiveCommunicationLocation string
param embeddingDeploymentType string = 'Standard'
param embeddingDimensions int = 3072
param embeddingModel string = 'text-embedding-3-large'
param embeddingQuota int = 4
param embeddingVersion string = '1'
param imageVersion string
param instance string
param llmFastContext int = 128000
param llmFastDeploymentType string = 'GlobalStandard'
param llmFastModel string = 'gpt-4o-mini'
param llmFastQuota int = 4
param llmFastVersion string = '2024-07-18'
param llmSlowContext int = 128000
param llmSlowDeploymentType string = 'GlobalStandard'
param llmSlowModel string = 'gpt-4o'
param llmSlowQuota int = 2
param llmSlowVersion string = '2024-08-06'
param openaiLocation string
param promptContentFilter bool = true
param searchLocation string
param resourceGroupName string
param location string = deployment().location

var tags = {
  application: 'swaraaus'
  instance: instance
  managed_by: 'Bicep'
  sources: 'https://github.com/prabhujigit/swara'
  version: imageVersion
}

resource existingRG 'Microsoft.Resources/resourceGroups@2021-04-01' existing = {
  name: resourceGroupName
}

module app 'app.bicep' = {
  name: instance
  scope: existingRG
  params: {
    cognitiveCommunicationLocation: cognitiveCommunicationLocation
    embeddingDeploymentType: embeddingDeploymentType
    embeddingDimensions: embeddingDimensions
    embeddingModel: embeddingModel
    embeddingQuota: embeddingQuota
    embeddingVersion: embeddingVersion
    imageVersion: imageVersion
    llmFastContext: llmFastContext
    llmFastDeploymentType: llmFastDeploymentType
    llmFastModel: llmFastModel
    llmFastQuota: llmFastQuota
    llmFastVersion: llmFastVersion
    llmSlowContext: llmSlowContext
    llmSlowDeploymentType: llmSlowDeploymentType
    llmSlowModel: llmSlowModel
    llmSlowQuota: llmSlowQuota
    llmSlowVersion: llmSlowVersion
    location: location
    openaiLocation: openaiLocation
    promptContentFilter: promptContentFilter
    searchLocation: searchLocation
    tags: tags
  }
}

output appUrl string = app.outputs.appUrl
output blobStoragePublicName string = app.outputs.blobStoragePublicName
output containerAppName string = app.outputs.containerAppName
output logAnalyticsCustomerId string = app.outputs.logAnalyticsCustomerId