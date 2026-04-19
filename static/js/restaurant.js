console.log("restaurant.js loaded");

// FORCE global scope
window.addFood = function () {
  alert("addFood triggered");

  fetch("/restaurant/api/add-food", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      name: document.getElementById("name").value,
      original_price: document.getElementById("original_price").value,
      price: document.getElementById("price").value,
      quantity: document.getElementById("quantity").value,
      pickup_start: document.getElementById("pickup_start").value,
      pickup_end: document.getElementById("pickup_end").value,
      food_type: document.getElementById("food_type").value   // ✅ NEW
    })
  })
  .then(res => res.json())
  .then(data => {
    alert("Response received");

    if (data.success) {
      alert("Food added successfully");
      window.location.href = "/restaurant/dashboard";
    } else {
      alert(data.error || "Backend error");
    }
  })
  .catch(err => {
    console.error(err);
    alert("Network error");
  });
};
