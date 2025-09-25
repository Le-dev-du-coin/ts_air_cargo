/**
 * TS Air Cargo - JavaScript Principal
 * Version: 1.0
 * Description: Fonctionnalités JavaScript globales pour TS Air Cargo
 */

// ============================================
// UTILITAIRES GLOBAUX
// ============================================

const TSAirCargo = {
    // Configuration globale
    config: {
        apiBaseUrl: '/api/',
        timeout: 10000,
        retryCount: 3
    },

    // Utilitaires
    utils: {
        // Format prix en FCFA
        formatPrice: function(price) {
            if (!price && price !== 0) return '0';
            return new Intl.NumberFormat('fr-FR').format(Math.round(price)) + ' FCFA';
        },

        // Format date française
        formatDate: function(dateString) {
            if (!dateString) return '-';
            const date = new Date(dateString);
            return date.toLocaleDateString('fr-FR', {
                day: '2-digit',
                month: '2-digit', 
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        },

        // Débounce pour optimiser les requêtes
        debounce: function(func, wait) {
            let timeout;
            return function executedFunction(...args) {
                const later = () => {
                    clearTimeout(timeout);
                    func(...args);
                };
                clearTimeout(timeout);
                timeout = setTimeout(later, wait);
            };
        },

        // Copy to clipboard
        copyToClipboard: function(text) {
            if (navigator.clipboard) {
                navigator.clipboard.writeText(text).then(() => {
                    TSAirCargo.notifications.show('Copié dans le presse-papiers', 'success');
                });
            } else {
                // Fallback pour navigateurs plus anciens
                const textArea = document.createElement('textarea');
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                TSAirCargo.notifications.show('Copié dans le presse-papiers', 'success');
            }
        },

        // Génération d'UUID simple
        generateId: function() {
            return Date.now().toString(36) + Math.random().toString(36).substr(2);
        }
    },

    // Système de notifications toast
    notifications: {
        show: function(message, type = 'info', duration = 4000) {
            const container = document.getElementById('toast-container') || this.createContainer();
            const toast = this.createToast(message, type, duration);
            container.appendChild(toast);
            
            // Animation d'entrée
            setTimeout(() => toast.classList.add('show'), 100);
            
            // Suppression automatique
            setTimeout(() => {
                toast.classList.remove('show');
                setTimeout(() => container.removeChild(toast), 300);
            }, duration);
        },

        createContainer: function() {
            const container = document.createElement('div');
            container.id = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 9999;
                max-width: 350px;
            `;
            document.body.appendChild(container);
            return container;
        },

        createToast: function(message, type, duration) {
            const toast = document.createElement('div');
            const icons = {
                success: 'bi-check-circle-fill',
                error: 'bi-x-circle-fill',
                warning: 'bi-exclamation-triangle-fill',
                info: 'bi-info-circle-fill'
            };
            
            toast.className = `toast-modern toast-${type}`;
            toast.style.cssText = `
                display: flex;
                align-items: center;
                padding: 1rem 1.5rem;
                margin-bottom: 10px;
                background: white;
                border-radius: 0.75rem;
                box-shadow: 0 4px 25px rgba(0, 0, 0, 0.15);
                border-left: 4px solid var(--${type === 'error' ? 'danger' : type}-color);
                transform: translateX(400px);
                transition: transform 0.3s ease;
                font-weight: 500;
            `;
            
            toast.innerHTML = `
                <i class="bi ${icons[type]} me-2" style="color: var(--${type === 'error' ? 'danger' : type}-color); font-size: 1.2rem;"></i>
                <span>${message}</span>
                <button type="button" class="btn-close ms-auto" style="font-size: 0.8rem;"></button>
            `;
            
            // Gestion fermeture
            toast.querySelector('.btn-close').addEventListener('click', () => {
                toast.style.transform = 'translateX(400px)';
                setTimeout(() => toast.remove(), 300);
            });
            
            return toast;
        }
    },

    // Confirmations modales
    confirmAction: function(message, callback, title = 'Confirmation', confirmText = 'Confirmer') {
        const modalId = 'confirm-modal-' + this.utils.generateId();
        const modalHtml = `
            <div class="modal fade" id="${modalId}" tabindex="-1">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Annuler</button>
                            <button type="button" class="btn btn-primary confirm-btn">${confirmText}</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        const modal = new bootstrap.Modal(document.getElementById(modalId));
        
        // Gestion confirmation
        document.querySelector(`#${modalId} .confirm-btn`).addEventListener('click', () => {
            callback();
            modal.hide();
        });
        
        // Nettoyage après fermeture
        document.getElementById(modalId).addEventListener('hidden.bs.modal', function() {
            this.remove();
        });
        
        modal.show();
    },

    // Gestion des formulaires
    forms: {
        // Validation en temps réel
        setupRealTimeValidation: function(formSelector) {
            const form = document.querySelector(formSelector);
            if (!form) return;
            
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                input.addEventListener('blur', function() {
                    TSAirCargo.forms.validateField(this);
                });
                
                input.addEventListener('input', TSAirCargo.utils.debounce(function() {
                    if (this.classList.contains('is-invalid') || this.classList.contains('is-valid')) {
                        TSAirCargo.forms.validateField(this);
                    }
                }, 500));
            });
        },

        // Validation d'un champ
        validateField: function(field) {
            const isValid = field.checkValidity();
            field.classList.remove('is-valid', 'is-invalid');
            field.classList.add(isValid ? 'is-valid' : 'is-invalid');
            
            // Gestion des messages d'erreur personnalisés
            const feedback = field.parentElement.querySelector('.invalid-feedback');
            if (feedback && !isValid) {
                feedback.textContent = field.validationMessage;
            }
        },

        // Soumission avec loading
        submitWithLoading: function(form, callback) {
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            
            // État loading
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<span class="loading-spinner me-2"></span>Traitement...';
            
            // Exécuter callback
            Promise.resolve(callback()).finally(() => {
                // Restaurer état normal
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            });
        }
    },

    // Gestion des données
    api: {
        // Requête GET générique
        get: async function(url, options = {}) {
            try {
                const response = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        ...options.headers
                    },
                    ...options
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('API GET Error:', error);
                TSAirCargo.notifications.show('Erreur de connexion', 'error');
                throw error;
            }
        },

        // Requête POST générique
        post: async function(url, data, options = {}) {
            try {
                const response = await fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest',
                        'X-CSRFToken': TSAirCargo.utils.getCsrfToken(),
                        ...options.headers
                    },
                    body: JSON.stringify(data),
                    ...options
                });
                
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                return await response.json();
            } catch (error) {
                console.error('API POST Error:', error);
                TSAirCargo.notifications.show('Erreur lors de l\'envoi', 'error');
                throw error;
            }
        }
    },

    // Initialisation
    init: function() {
        // Vérification des dépendances
        if (typeof bootstrap === 'undefined') {
            console.warn('Bootstrap JavaScript non détecté');
        }
        
        // Configuration globale des tooltips Bootstrap
        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggerList.map(function (tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
        
        // Gestion des confirmations automatiques
        document.addEventListener('click', function(e) {
            if (e.target.hasAttribute('data-confirm')) {
                e.preventDefault();
                const message = e.target.getAttribute('data-confirm');
                const href = e.target.getAttribute('href') || e.target.closest('a')?.getAttribute('href');
                
                TSAirCargo.confirmAction(message, () => {
                    if (href) window.location.href = href;
                });
            }
        });
        
        // Auto-format des prix
        document.addEventListener('input', function(e) {
            if (e.target.classList.contains('price-input')) {
                const value = parseFloat(e.target.value);
                if (!isNaN(value)) {
                    const preview = document.querySelector(e.target.getAttribute('data-preview'));
                    if (preview) {
                        preview.textContent = TSAirCargo.utils.formatPrice(value);
                    }
                }
            }
        });
        
        // Copie automatique des numéros de suivi
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('tracking-number')) {
                TSAirCargo.utils.copyToClipboard(e.target.textContent);
            }
        });

        console.log('✅ TS Air Cargo JavaScript initialisé');
    }
};

// ============================================
// FONCTIONS UTILITAIRES GLOBALES
// ============================================

// Récupération du token CSRF Django
TSAirCargo.utils.getCsrfToken = function() {
    const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
    return cookie ? cookie.split('=')[1] : document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
};

// Ajout de classe show pour les toasts
const style = document.createElement('style');
style.textContent = `
    .toast-modern.show {
        transform: translateX(0) !important;
    }
    
    .loading-spinner {
        display: inline-block;
        width: 16px;
        height: 16px;
        border: 2px solid #f3f4f6;
        border-top: 2px solid currentColor;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);

// ============================================
// INITIALISATION AU CHARGEMENT
// ============================================

// Initialisation quand le DOM est prêt
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', TSAirCargo.init);
} else {
    TSAirCargo.init();
}

// Exposition globale pour utilisation dans d'autres scripts
window.TSAirCargo = TSAirCargo;