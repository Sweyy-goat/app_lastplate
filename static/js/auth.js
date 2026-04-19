function signup() {
  const name = document.getElementById("name");
  const mobile = document.getElementById("mobile");
  const password = document.getElementById("password");

  if (!name || !mobile || !password) return;

  fetch("/api/user/signup", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      name: name.value,
      mobile: mobile.value,
      password: password.value
    })
  })
  .then(res => res.json())
  .then(data => {
    alert(data.success ? "Signup successful" : data.message);
    if (data.success) window.location.href = "/login";
  });
}

function userLogin() {
  const mobile = document.getElementById("mobile");
  const password = document.getElementById("password");

  if (!mobile || !password) return;

  fetch("/api/user/login", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      mobile: mobile.value,
      password: password.value
    })
  })
  .then(res => res.json())
  .then(data => {
    alert(data.success ? "Login successful" : "Invalid credentials");
    if (data.success) window.location.href = "/browse";
  });
}

function restaurantLogin() {
  const mobile = document.getElementById("mobile");
  const password = document.getElementById("password");

  if (!mobile || !password) return;

  fetch("/api/restaurant/login", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      mobile: mobile.value,
      password: password.value
    })
  })
  .then(res => res.json())
  .then(data => {
    alert(data.success ? "Login successful" : "Invalid credentials");
    if (data.success) window.location.href = "/restaurant/dashboard";
  });
}
