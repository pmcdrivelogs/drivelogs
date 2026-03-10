// Toggle password visibility
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('password');
    const toggleBtn = document.getElementById('toggleBtn');
    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        toggleBtn.textContent = '🙈';
    } else {
        passwordInput.type = 'password';
        toggleBtn.textContent = '👁️';
    }
}

// Activate login button
const loginForm = document.getElementById('loginForm');
if (loginForm) {
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        alert('Login button clicked!');
    });
}

// Attach toggle to button
const toggleBtn = document.getElementById('toggleBtn');
if (toggleBtn) {
    toggleBtn.addEventListener('click', togglePasswordVisibility);
}
