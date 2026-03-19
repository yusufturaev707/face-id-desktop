import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from services.auth_service import AuthService
from services.face_engine import FaceEngineLoader
from ui.styles import GLOBAL_STYLESHEET
from ui.pages.login_page import LoginPage


class MainWindow(QMainWindow):
    PAGE_LOGIN = 0
    PAGE_SYNC = 1
    PAGE_MODE = 2
    PAGE_SESSION = 3
    PAGE_FACEID = 4

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Face-ID Desktop")
        self.setMinimumSize(1100, 700)

        self._auth = AuthService()
        self._mode = "offline"

        # Stacked pages
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Page 1: Login (loaded immediately)
        self._login_page = LoginPage(self._auth)
        self._login_page.login_success.connect(self._on_login_success)
        self._login_page.exit_requested.connect(self._on_exit)
        self._stack.addWidget(self._login_page)

        # Start at login
        self._stack.setCurrentIndex(self.PAGE_LOGIN)

        # Lazy page references
        self._sync_page = None
        self._mode_page = None
        self._session_page = None
        self._faceid_page = None

        # Start loading InsightFace model in background
        self._model_loader = FaceEngineLoader()
        self._model_loader.progress.connect(self._on_model_progress)
        self._model_loader.finished.connect(self._on_model_loaded)
        self._model_loader.start()

    def _on_model_progress(self, msg: str):
        self._login_page.set_model_status(msg)

    def _on_model_loaded(self, success: bool, msg: str):
        self._login_page.set_model_status(
            "AI model tayyor" if success else msg,
            is_ready=success,
        )
        self._model_loader = None

    def _ensure_pages_loaded(self):
        """Load remaining pages on demand (after login)."""
        if self._sync_page is not None:
            return
        from ui.pages.sync_page import SyncPage
        from ui.pages.mode_page import ModePage
        from ui.pages.session_page import SessionPage
        from ui.pages.faceid_page import FaceIDPage

        self._sync_page = SyncPage()
        self._sync_page.sync_complete.connect(self._on_sync_complete)
        self._sync_page.logout_requested.connect(self._on_logout)
        self._stack.addWidget(self._sync_page)

        self._mode_page = ModePage()
        self._mode_page.mode_selected.connect(self._on_mode_selected)
        self._mode_page.logout_requested.connect(self._on_logout)
        self._mode_page.go_back.connect(lambda: self._stack.setCurrentIndex(self.PAGE_SYNC))
        self._stack.addWidget(self._mode_page)

        self._session_page = SessionPage()
        self._session_page.session_selected.connect(self._on_session_selected)
        self._session_page.logout_requested.connect(self._on_logout)
        self._session_page.go_back.connect(lambda: self._stack.setCurrentIndex(self.PAGE_MODE))
        self._stack.addWidget(self._session_page)

        self._faceid_page = FaceIDPage()
        self._faceid_page.logout_requested.connect(self._on_logout)
        self._faceid_page.go_back.connect(self._on_back_from_faceid)
        self._stack.addWidget(self._faceid_page)

    def _on_login_success(self, staff: dict):
        self._staff = staff
        self._ensure_pages_loaded()
        self._stack.setCurrentIndex(self.PAGE_SYNC)

    def _on_sync_complete(self):
        self._stack.setCurrentIndex(self.PAGE_MODE)

    def _on_mode_selected(self, mode: str):
        self._mode = mode
        self._stack.setCurrentIndex(self.PAGE_SESSION)

    def _on_session_selected(self, session_sm_id: int):
        self._faceid_page.setup_session(
            session_sm_id=session_sm_id,
            staff_id=self._staff["id"],
            mode=self._mode,
        )
        self._stack.setCurrentIndex(self.PAGE_FACEID)

    def _on_back_from_faceid(self):
        """Cleanup camera/sync before going back."""
        self._faceid_page.cleanup()
        self._stack.setCurrentIndex(self.PAGE_SESSION)

    def _on_logout(self):
        """Logout and return to login page."""
        if self._faceid_page:
            self._faceid_page.cleanup()
        self._auth.logout()
        self._login_page.username_input.clear()
        self._login_page.password_input.clear()
        self._login_page.error_label.setText("")
        self._stack.setCurrentIndex(self.PAGE_LOGIN)

    def _on_exit(self):
        """Exit the application."""
        self.close()

    def closeEvent(self, event):
        if self._faceid_page:
            self._faceid_page.cleanup()
        from database.db_manager import DatabaseManager
        DatabaseManager().close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 12))
    app.setStyleSheet(GLOBAL_STYLESHEET)

    window = MainWindow()
    window.showFullScreen()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
