package com.example.earlywarningsystem.ui.admin

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import kotlinx.coroutines.launch
import androidx.compose.ui.unit.dp
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import com.example.earlywarningsystem.data.model.Recipient

@Composable
fun AdminScreen(
    viewModel: AdminViewModel,
    modifier: Modifier = Modifier
) {
    val recipients by viewModel.recipients.collectAsState()
    val snackbarHostState = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    var showAddDialog by remember { mutableStateOf(false) }
    var editingRecipient by remember { mutableStateOf<Recipient?>(null) }
    var deleteConfirm by remember { mutableStateOf<Recipient?>(null) }

    Box(
        modifier = modifier
            .fillMaxSize()
            .padding(PaddingValues(horizontal = 20.dp, vertical = 16.dp))
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                text = "SMS recipients",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                text = "Manage recipients for SMS alerts",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 8.dp)
            ) {
                items(recipients) { r ->
                    Card(
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.6f)
                        )
                    ) {
                        Column(modifier = Modifier.padding(12.dp)) {
                            Text(
                                text = r.name,
                                style = MaterialTheme.typography.titleMedium,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = r.phone,
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Text(
                                text = if (r.active) "Active" else "Inactive",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Row(
                                horizontalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                IconButton(onClick = { editingRecipient = r }) {
                                    Icon(Icons.Default.Edit, contentDescription = "Edit")
                                }
                                IconButton(onClick = { deleteConfirm = r }) {
                                    Icon(Icons.Default.Delete, contentDescription = "Delete")
                                }
                            }
                        }
                    }
                }
            }
        }

        FloatingActionButton(
            onClick = { showAddDialog = true },
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(16.dp)
        ) {
            Icon(Icons.Default.Add, contentDescription = "Add recipient")
        }

        SnackbarHost(
            hostState = snackbarHostState,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 80.dp)
        )
    }

    if (showAddDialog) {
        RecipientDialog(
            recipient = null,
            onDismiss = { showAddDialog = false },
            onSave = { name, phone, active ->
                viewModel.addRecipient(name, phone, active) {
                    it.onSuccess {
                        showAddDialog = false
                        scope.launch { snackbarHostState.showSnackbar("Added") }
                    }.onFailure {
                        scope.launch { snackbarHostState.showSnackbar(it.message ?: "Failed") }
                    }
                }
            }
        )
    }

    editingRecipient?.let { r ->
        RecipientDialog(
            recipient = r,
            onDismiss = { editingRecipient = null },
            onSave = { name, phone, active ->
                viewModel.updateRecipient(r.id, name, phone, active) {
                    it.onSuccess {
                        editingRecipient = null
                        scope.launch { snackbarHostState.showSnackbar("Updated") }
                    }.onFailure {
                        scope.launch { snackbarHostState.showSnackbar(it.message ?: "Failed") }
                    }
                }
            }
        )
    }

    deleteConfirm?.let { r ->
        AlertDialog(
            onDismissRequest = { deleteConfirm = null },
            title = { Text("Delete recipient?") },
            text = { Text("Remove ${r.name} (${r.phone})?") },
            confirmButton = {
                Button(
                    onClick = {
                        viewModel.deleteRecipient(r.id) {
                            it.onSuccess {
                                deleteConfirm = null
                                scope.launch { snackbarHostState.showSnackbar("Deleted") }
                            }.onFailure {
                                scope.launch { snackbarHostState.showSnackbar(it.message ?: "Failed") }
                            }
                        }
                    }
                ) {
                    Text("Delete")
                }
            },
            dismissButton = {
                TextButton(onClick = { deleteConfirm = null }) {
                    Text("Cancel")
                }
            }
        )
    }
}

@Composable
private fun RecipientDialog(
    recipient: Recipient?,
    onDismiss: () -> Unit,
    onSave: (name: String, phone: String, active: Boolean) -> Unit
) {
    var name by remember(recipient) { mutableStateOf(recipient?.name ?: "") }
    var phone by remember(recipient) { mutableStateOf(recipient?.phone ?: "") }
    var active by remember(recipient) { mutableStateOf(recipient?.active ?: true) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (recipient == null) "Add recipient" else "Edit recipient") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = phone,
                    onValueChange = { phone = it },
                    label = { Text("Phone") },
                    modifier = Modifier.fillMaxWidth()
                )
                if (recipient != null) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Text("Active")
                        androidx.compose.material3.Switch(
                            checked = active,
                            onCheckedChange = { active = it }
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(name, phone, active) }
            ) {
                Text(if (recipient == null) "Add" else "Save")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("Cancel")
            }
        }
    )
}
