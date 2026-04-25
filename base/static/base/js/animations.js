/* animations.js - UI Animation Handlers */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Intersection Observer for Scroll Reveals
    const revealOptions = {
        root: null,
        rootMargin: '0px 0px -50px 0px', // Trigger slightly before element comes fully into view
        threshold: 0.05 // Very low threshold to ensure it triggers even for tall elements
    };

    const revealObserver = new IntersectionObserver((entries, observer) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
                
                // Trigger count-up if element has data-count-to
                if (entry.target.hasAttribute('data-count-to')) {
                    startCountUp(entry.target);
                }

                // Stop observing once revealed to prevent re-triggering
                observer.unobserve(entry.target);
            }
        });
    }, revealOptions);

    // Attach observer to all elements with reveal classes
    const revealElements = document.querySelectorAll('.reveal, .reveal-up, .reveal-slide-up, .count-up-element');
    revealElements.forEach(el => revealObserver.observe(el));

    // 2. Count-Up Logic
    function startCountUp(element) {
        const targetStr = element.getAttribute('data-count-to');
        if (!targetStr) return;
        
        // Match prefix, number, suffix (e.g., "$", "1,500", "+")
        const match = targetStr.match(/^([^\d]*)?([\d,.]+)([^\d]*)?$/);
        if (!match) {
            // Fallback for purely non-numeric or strange formats
            element.textContent = targetStr;
            return;
        }

        const prefix = match[1] || '';
        const numStr = match[2].replace(/,/g, '');
        const suffix = match[3] || '';
        
        const targetVal = parseFloat(numStr);
        if (isNaN(targetVal)) return;

        const duration = parseInt(element.getAttribute('data-duration') || '1500', 10);
        const startTime = performance.now();
        const startVal = 0;

        function updateCount(currentTime) {
            const elapsedTime = currentTime - startTime;
            let progress = elapsedTime / duration;
            
            if (progress > 1) progress = 1;

            // Ease out quad
            const easeOutProgress = progress * (2 - progress);
            
            let currentVal = startVal + (targetVal - startVal) * easeOutProgress;
            
            let displayVal;
            // Format number based on if target was an integer or had decimals
            if (targetVal % 1 !== 0) {
                displayVal = currentVal.toFixed(1);
            } else {
                displayVal = Math.round(currentVal).toLocaleString();
            }
            
            element.textContent = prefix + displayVal + suffix;

            if (progress < 1) {
                requestAnimationFrame(updateCount);
            } else {
                // Ensure exact final string is set
                element.textContent = targetStr;
            }
        }

        requestAnimationFrame(updateCount);
    }

    // 3. Navbar Scroll Effect (Landing Page primarily)
    const header = document.getElementById('header');
    if (header) {
        const handleScroll = () => {
            if (window.scrollY > 60) {
                header.classList.add('nav-scrolled');
            } else {
                header.classList.remove('nav-scrolled');
            }
        };
        
        // Initial check
        handleScroll();
        
        // Listen to scroll
        window.addEventListener('scroll', handleScroll, { passive: true });
    }

    // 4. Trigger Ring Animation on Profile Load
    const completionRing = document.querySelector('.completion-ring');
    if (completionRing) {
        const strongTag = completionRing.querySelector('strong');
        let targetPercent = 0;
        
        if (strongTag) {
            const dataTo = strongTag.getAttribute('data-count-to');
            targetPercent = parseInt(dataTo || strongTag.textContent, 10);
        }
        
        // Slight delay to ensure smooth rendering after page load
        setTimeout(() => {
            animateRing(completionRing, targetPercent);
        }, 300);
    }

    function animateRing(element, target) {
        const duration = 1500;
        const startTime = performance.now();

        function step(currentTime) {
            const elapsed = currentTime - startTime;
            let progress = Math.min(elapsed / duration, 1);
            
            // Ease out cubic
            const easeProgress = 1 - Math.pow(1 - progress, 3);
            const currentPercent = easeProgress * target;
            
            element.style.setProperty('--percent', `${currentPercent}%`);

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        }
        requestAnimationFrame(step);
    }
});
