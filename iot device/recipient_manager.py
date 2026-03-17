"""
Main recipient management orchestrator.
Handles initialization, synchronization, and provides unified interface.
"""

from recipient_storage import (
    init_database,
    ensure_default_recipient,
    get_all_recipients,
    get_active_phone_numbers,
    get_recipient_count
)
from firebase_recipient_sync import sync_recipients, check_internet_connection
import threading
import time

# =====================================================
# CONFIGURATION
# =====================================================
SYNC_INTERVAL_SECONDS = 300  # 5 minutes
AUTO_SYNC_ENABLED = True

# =====================================================
# RECIPIENT MANAGER CLASS
# =====================================================
class RecipientManager:
    """
    Main recipient management system.
    Handles initialization, synchronization, and provides unified interface.
    """
    
    def __init__(self, auto_sync=True, sync_interval=SYNC_INTERVAL_SECONDS):
        """
        Initialize recipient manager.
        
        Args:
            auto_sync: Enable automatic synchronization
            sync_interval: Sync interval in seconds
        """
        self.auto_sync = auto_sync
        self.sync_interval = sync_interval
        self.sync_thread = None
        self.running = False
    
    def initialize(self):
        """
        Initialize the recipient management system.
        - Initialize local database
        - Ensure default recipient exists
        - Perform initial sync from Firebase
        """
        print("[INFO] Initializing recipient management system...")
        
        # Initialize local database
        if not init_database():
            print("[ERROR] Failed to initialize database")
            return False
        
        # Ensure default recipient exists
        ensure_default_recipient()
        
        # Perform initial sync from Firebase
        print("🔄 Performing initial sync from Firebase...")
        if check_internet_connection():
            sync_recipients()
        else:
            print("[WARN] No internet connection. Using local database only.")
        
        # Print status
        active_count = get_recipient_count(active_only=True)
        print(f"[INFO] System initialized. Active recipients: {active_count}")
        
        return True
    
    def start_auto_sync(self):
        """Start automatic synchronization in background thread"""
        if not self.auto_sync:
            return
        
        if self.running:
            print("[WARN] Auto-sync already running")
            return
        
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        print(f"🔄 Auto-sync started (interval: {self.sync_interval}s)")
    
    def stop_auto_sync(self):
        """Stop automatic synchronization"""
        self.running = False
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        print("🛑 Auto-sync stopped")
    
    def _sync_loop(self):
        """Background sync loop"""
        while self.running:
            try:
                time.sleep(self.sync_interval)
                if self.running and check_internet_connection():
                    sync_recipients()
            except Exception as e:
                print(f"[ERROR] Error in sync loop: {e}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def manual_sync(self):
        """
        Manually trigger synchronization from Firebase.
        
        Returns:
            dict: Sync statistics
        """
        return sync_recipients()
    
    def get_recipients(self, active_only=True):
        """
        Get all recipients from local database.
        
        Args:
            active_only: If True, return only active recipients
        
        Returns:
            list: List of recipient tuples
        """
        return get_all_recipients(active_only=active_only)
    
    def get_phone_numbers(self):
        """
        Get list of active phone numbers for SMS alerts.
        
        Returns:
            list: List of phone number strings
        """
        return get_active_phone_numbers()
    
    def get_status(self):
        """
        Get system status.
        
        Returns:
            dict: Status information
        """
        return {
            'total_recipients': get_recipient_count(active_only=False),
            'active_recipients': get_recipient_count(active_only=True),
            'internet_available': check_internet_connection(),
            'auto_sync_enabled': self.auto_sync,
            'auto_sync_running': self.running
        }

# =====================================================
# GLOBAL INSTANCE (SINGLETON PATTERN)
# =====================================================
_manager_instance = None

def get_recipient_manager(auto_sync=AUTO_SYNC_ENABLED, sync_interval=SYNC_INTERVAL_SECONDS):
    """
    Get or create global recipient manager instance.
    
    Args:
        auto_sync: Enable automatic synchronization
        sync_interval: Sync interval in seconds
    
    Returns:
        RecipientManager: Global manager instance
    """
    global _manager_instance
    
    if _manager_instance is None:
        _manager_instance = RecipientManager(auto_sync=auto_sync, sync_interval=sync_interval)
        _manager_instance.initialize()
        if auto_sync:
            _manager_instance.start_auto_sync()
    
    return _manager_instance

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("RECIPIENT MANAGEMENT SYSTEM")
    print("=" * 60)
    print()
    
    # Initialize and start manager
    manager = get_recipient_manager(auto_sync=True, sync_interval=300)
    
    # Print status
    status = manager.get_status()
    print("\n[INFO] System status:")
    for key, value in status.items():
        print(f"   {key}: {value}")
    
    # Keep running
    try:
        print("\n[INFO] System running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping system...")
        manager.stop_auto_sync()
        print("[INFO] System stopped.")
