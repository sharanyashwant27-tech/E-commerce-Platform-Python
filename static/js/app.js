/* ShopSphere storefront helpers */
document.addEventListener("DOMContentLoaded", () => {
  const alerts = document.querySelectorAll(".alert-dismissible");
  alerts.forEach((el) => {
    setTimeout(() => el.classList.add("fade"), 4000);
  });
});
