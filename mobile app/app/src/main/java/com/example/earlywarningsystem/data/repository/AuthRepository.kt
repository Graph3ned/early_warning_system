package com.example.earlywarningsystem.data.repository

import com.example.earlywarningsystem.data.model.UserRole
import com.google.firebase.auth.EmailAuthProvider
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseUser
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.database.ValueEventListener
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.tasks.await

class AuthRepository {
    private val auth = FirebaseAuth.getInstance()
    private val database = FirebaseDatabase.getInstance().reference

    val currentUser: FirebaseUser?
        get() = auth.currentUser

    fun isLoggedIn(): Boolean = currentUser != null

    suspend fun getCurrentUserRole(): UserRole {
        val uid = currentUser?.uid ?: return UserRole.VIEWER
        return try {
            val snapshot = database.child("users").child(uid).child("role").get().await()
            val role = snapshot.getValue(String::class.java)?.lowercase() ?: "viewer"
            when (role) {
                "admin" -> UserRole.ADMIN
                else -> UserRole.VIEWER
            }
        } catch (_: Exception) {
            UserRole.VIEWER
        }
    }

    /** Emits the current auth user's UID whenever it changes (login/logout). */
    fun currentUserIdFlow(): Flow<String?> = callbackFlow {
        val listener = FirebaseAuth.AuthStateListener { trySend(it.currentUser?.uid) }
        auth.addAuthStateListener(listener)
        awaitClose { auth.removeAuthStateListener(listener) }
    }

    /** Listens to role for a specific user. Use with currentUserIdFlow() so role updates when user changes. */
    fun roleFlowForUser(uid: String): Flow<UserRole> = callbackFlow {
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val role = snapshot.getValue(String::class.java)?.lowercase() ?: "viewer"
                trySend(if (role == "admin") UserRole.ADMIN else UserRole.VIEWER)
            }
            override fun onCancelled(error: DatabaseError) {
                trySend(UserRole.VIEWER)
            }
        }
        database.child("users").child(uid).child("role").addValueEventListener(listener)
        awaitClose {
            database.child("users").child(uid).child("role").removeEventListener(listener)
        }
    }

    /** Role for the currently logged-in user. Re-subscribes when user changes (fixes wrong role after login). */
    fun currentUserRoleFlow(): Flow<UserRole> = callbackFlow {
        val uid = currentUser?.uid
        if (uid == null) {
            trySend(UserRole.VIEWER)
            close()
            return@callbackFlow
        }
        val listener = object : ValueEventListener {
            override fun onDataChange(snapshot: DataSnapshot) {
                val role = snapshot.getValue(String::class.java)?.lowercase() ?: "viewer"
                trySend(
                    if (role == "admin") UserRole.ADMIN else UserRole.VIEWER
                )
            }
            override fun onCancelled(error: DatabaseError) {
                trySend(UserRole.VIEWER)
            }
        }
        database.child("users").child(uid).child("role").addValueEventListener(listener)
        awaitClose {
            database.child("users").child(uid).child("role").removeEventListener(listener)
        }
    }

    suspend fun signIn(email: String, password: String): Result<Unit> = runCatching {
        auth.signInWithEmailAndPassword(email, password).await()
        if (auth.currentUser == null) throw IllegalStateException("Sign in failed")
    }

    suspend fun register(email: String, password: String): Result<Unit> = runCatching {
        val result = auth.createUserWithEmailAndPassword(email, password).await()
        val user = result.user ?: throw IllegalStateException("Registration failed")
        database.child("users").child(user.uid).child("role").setValue("viewer").await()
    }

    fun signOut() {
        auth.signOut()
    }

    fun getCurrentUserEmail(): String? = currentUser?.email

    suspend fun reauthenticate(email: String, password: String): Result<Unit> = runCatching {
        val user = currentUser ?: throw IllegalStateException("Not logged in")
        val credential = EmailAuthProvider.getCredential(email, password)
        user.reauthenticate(credential).await()
    }

    suspend fun updateEmail(newEmail: String): Result<Unit> = runCatching {
        val user = currentUser ?: throw IllegalStateException("Not logged in")
        user.updateEmail(newEmail).await()
    }

    suspend fun updatePassword(newPassword: String): Result<Unit> = runCatching {
        val user = currentUser ?: throw IllegalStateException("Not logged in")
        user.updatePassword(newPassword).await()
    }
}
