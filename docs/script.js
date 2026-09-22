// Smooth scrolling for anchor links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Optional: Add a simple copy button functionality for the JSON code block
const codeBlock = document.querySelector('pre');
if (codeBlock) {
    codeBlock.addEventListener('click', async () => {
        const text = codeBlock.innerText;
        try {
            await navigator.clipboard.writeText(text);
            const originalBg = codeBlock.style.backgroundColor;
            codeBlock.style.backgroundColor = 'rgba(99, 102, 241, 0.2)';
            setTimeout(() => {
                codeBlock.style.backgroundColor = originalBg;
            }, 300);
        } catch (err) {
            console.error('Failed to copy text: ', err);
        }
    });
    codeBlock.style.cursor = 'pointer';
    codeBlock.title = 'Click to copy';
}
