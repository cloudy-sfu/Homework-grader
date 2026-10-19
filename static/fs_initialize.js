async function bind_fs(fs_url) {
    const response = await fetch(fs_url);
    if (response.ok) {
        const get_params = new URLSearchParams(fs_url.split('?')[1]);
        const fs_element_id = get_params.get("container_id");
        document.getElementById(fs_element_id).innerHTML = await response.text();
    }
}

// Set a CSS variable with the initial window width
document.documentElement.style.setProperty('--window-width',
    `${window.innerWidth}px`);
// Update the CSS variable on window resize
window.addEventListener('resize', () => {
    document.documentElement.style.setProperty('--window-width',
        `${window.innerWidth}px`);
});

function get_path_fs(fs_element_id) {
    return document.getElementById(fs_element_id).querySelector("nav > current_folder").textContent;
}

function filter_dropdown(inputElement) {
    let inputText = inputElement.value.toLowerCase();
    // Traverse to find the related dropdown items
    let dropdownItems = inputElement.closest('.nav-item').querySelectorAll('.dropdown-item');
    dropdownItems.forEach(function(item) {
        if (item.textContent.toLowerCase().includes(inputText)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}
