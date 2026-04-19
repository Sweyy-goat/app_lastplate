const foodList = document.getElementById("foodList");

if (foodList) {
  fetch("/api/foods")
    .then(res => res.json())
    .then(data => {
      foodList.innerHTML = ""; // clear old content

      data.foods.forEach(food => {
        const foodId = food[0];

        foodList.innerHTML += `
          <div style="border:1px solid #ccc; margin:10px; padding:10px">
            <h3>${food[1]}</h3>
            <p><strong>Restaurant:</strong> ${food[6]}</p>
            <p><strong>Price:</strong> ₹${food[2]}</p>
            <p><strong>Available:</strong> ${food[3]}</p>
            <p><strong>Pickup:</strong> ${food[4]} - ${food[5]}</p>

            <a href="/checkout/${foodId}">
              <button>Buy</button>
            </a>
          </div>
        `;
      });
    })
}

