let authToken = null;

function login() {
    const password = document.getElementById('admin-password').value;
    const errorP = document.getElementById('login-error');
    errorP.textContent = '';

    fetch('/admin', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams({ 'password': password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            authToken = password; // Use the password as a simple auth token
            document.getElementById('login-view').style.display = 'none';
            document.getElementById('dashboard-view').style.display = 'block';
            loadDashboardData();
        } else {
            errorP.textContent = data.message || 'Login failed.';
        }
    })
    .catch(err => {
        errorP.textContent = 'An error occurred.';
    });
}

function addProfileField() {
    const container = document.getElementById('profiles-container');
    const profileCount = container.children.length + 1;
    const newProfile = document.createElement('div');
    newProfile.className = 'profile-group';
    newProfile.innerHTML = `
        <input type="text" class="profile-name" placeholder="প্রোফাইলের নাম ${profileCount}">
        <input type="text" class="profile-password" placeholder="প্রোফাইলের পাসওয়ার্ড ${profileCount}">
    `;
    container.appendChild(newProfile);
}

async function loadDashboardData() {
    if (!authToken) return;

    try {
        const response = await fetch('/api/admin/data', {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });
        if (!response.ok) throw new Error('Failed to fetch data');

        const data = await response.json();
        
        // Populate users table
        const usersTable = document.getElementById('users-table').getElementsByTagName('tbody')[0];
        usersTable.innerHTML = '';
        data.users.forEach(user => {
            usersTable.innerHTML += `<tr>
                <td>${user.telegram_id}</td>
                <td>${user.username || 'N/A'}</td>
                <td>${user.referral_count}</td>
                <td>${user.has_access ? 'হ্যাঁ' : 'না'}</td>
            </tr>`;
        });

        // Populate accounts table
        const accountsTable = document.getElementById('accounts-table').getElementsByTagName('tbody')[0];
        accountsTable.innerHTML = '';
        data.accounts.forEach(account => {
            if (account.profiles.length === 0) {
                 accountsTable.innerHTML += `<tr>
                    <td>${account.netflix_email}</td>
                    <td colspan="3"><em>কোনো প্রোফাইল যোগ করা হয়নি</em></td>
                </tr>`;
            } else {
                account.profiles.forEach(profile => {
                    accountsTable.innerHTML += `<tr>
                        <td>${account.netflix_email}</td>
                        <td>${profile.profile_name}</td>
                        <td class="status-${profile.status}">${profile.status === 'available' ? 'খালি আছে' : 'ব্যবহৃত'}</td>
                        <td>${profile.assigned_to_user_id || 'N/A'}</td>
                    </tr>`;
                });
            }
        });

    } catch (error) {
        console.error('Error loading dashboard data:', error);
        alert('ড্যাশবোর্ডের তথ্য লোড করা যায়নি।');
    }
}

async function addAccount() {
    const profiles = [];
    document.querySelectorAll('.profile-group').forEach(group => {
        const name = group.querySelector('.profile-name').value;
        const pass = group.querySelector('.profile-password').value;
        if (name && pass) {
            profiles.push({ profile_name: name, profile_password: pass });
        }
    });

    const accountData = {
        netflix_email: document.getElementById('netflix-email').value,
        netflix_password: document.getElementById('netflix-password').value,
        gmail_account: document.getElementById('gmail-account').value,
        profiles: profiles
    };

    if (!accountData.netflix_email || profiles.length === 0) {
        alert('Netflix ইমেইল এবং অন্তত একটি প্রোফাইল অবশ্যই যোগ করতে হবে।');
        return;
    }

    try {
        const response = await fetch('/api/admin/accounts', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${authToken}`
            },
            body: JSON.stringify(accountData)
        });

        const result = await response.json();
        alert(result.message || result.error);
        if (response.ok) {
            loadDashboardData();
        }
    } catch (error) {
        console.error('Error adding account:', error);
        alert('অ্যাকাউন্ট যোগ করার সময় সমস্যা হয়েছে।');
    }
}

