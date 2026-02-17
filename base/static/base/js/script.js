document.addEventListener('DOMContentLoaded', function() {
    // Mobile menu toggle
    const mobileMenuBtn = document.getElementById('mobileMenu');
    const navMenu = document.getElementById('navMenu');

    function closeMenu() {
        navMenu.classList.remove('active');
        mobileMenuBtn.classList.remove('open');
        document.body.style.overflow = '';
    }

    // Toggle mobile menu
    mobileMenuBtn.addEventListener('click', function() {
        const isActive = navMenu.classList.toggle('active');
        this.classList.toggle('open', isActive);
        document.body.style.overflow = isActive ? 'hidden' : '';
    });

    // Close mobile menu when clicking a nav link
    const navLinks = document.querySelectorAll('.nav-links a, .mob-nav-item, .mob-auth-btn, .mob-auth-cta');
    navLinks.forEach(link => {
        link.addEventListener('click', closeMenu);
    });
    
    // Form tab switching (UI only)
    const tabs = document.querySelectorAll('.form-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            // Remove active class from all tabs and content
            document.querySelectorAll('.form-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.form-content').forEach(c => c.classList.remove('active'));
            
            // Add active class to clicked tab and corresponding content
            this.classList.add('active');
            const tabId = this.getAttribute('data-tab');
            document.getElementById(tabId + '-form').classList.add('active');
        });
    });
    
    // Header scroll effect
    const header = document.getElementById('header');
    window.addEventListener('scroll', function() {
        if (window.scrollY > 100) {
            header.classList.add('scrolled');
        } else {
            header.classList.remove('scrolled');
        }
    });
    
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();

            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 68,
                    behavior: 'smooth'
                });
            }
        });
    });
    
    // Animation for elements when they come into view
    const animateOnScroll = function() {
        const elements = document.querySelectorAll('.service-card, .feature, .about-img, .about-text');
        
        elements.forEach(element => {
            const elementPosition = element.getBoundingClientRect().top;
            const windowHeight = window.innerHeight;
            
            if (elementPosition < windowHeight - 100) {
                element.style.opacity = '1';
                element.style.transform = 'translateY(0)';
            }
        });
    };
    
    // Set initial state for animated elements
    document.querySelectorAll('.service-card, .feature, .about-img, .about-text').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    });
    
    // Run once on load
    animateOnScroll();
    
    // Run on scroll
    window.addEventListener('scroll', animateOnScroll);

    // Resume file size validation (max 5MB)
    const resumeInput = document.getElementById('resume');
    if (resumeInput) {
        resumeInput.addEventListener('change', function () {
            const file = this.files[0];
            const maxSizeMB = 5;

            if (file && file.size > maxSizeMB * 1024 * 1024) {
                alert('File size exceeds 5MB. Please upload a smaller file.');
                this.value = ''; // Clear the file input
            }
        });
    }

    // ✅ Add loading animation on register button
    const registrationForm = document.getElementById('registrationForm');
    const submitBtn = document.getElementById('submitBtn');

    if (registrationForm && submitBtn) {
        registrationForm.addEventListener('submit', function() {
            submitBtn.classList.add('loading');
            submitBtn.disabled = true;
        });
    }
});


document.addEventListener("DOMContentLoaded", function() {
    const messages = document.querySelectorAll(".message-box");

    messages.forEach((msg) => {
        // Close on click
        msg.querySelector(".close-btn").addEventListener("click", () => {
            msg.style.opacity = "0";
            setTimeout(() => msg.remove(), 300);
        });

        // Auto hide after 5 seconds
        setTimeout(() => {
            msg.style.opacity = "0";
            setTimeout(() => msg.remove(), 300);
        }, 5000);
    });
});
