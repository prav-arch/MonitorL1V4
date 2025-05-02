#!/bin/bash
# Script to fix Docker daemon socket permission issues

# Print colored output
print_info() {
    echo -e "\e[1;34m[INFO] $1\e[0m"
}

print_success() {
    echo -e "\e[1;32m[SUCCESS] $1\e[0m"
}

print_error() {
    echo -e "\e[1;31m[ERROR] $1\e[0m"
}

print_warning() {
    echo -e "\e[1;33m[WARNING] $1\e[0m"
}

# Display header
echo "============================================="
echo "  Docker Daemon Socket Permission Fix Tool   "
echo "============================================="
echo ""

# Check if script is run as root
if [ "$(id -u)" != "0" ]; then
   print_error "This script must be run as root (with sudo)"
   exit 1
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Installing Docker first..."
    
    # Install Docker
    print_info "Updating package index..."
    apt-get update

    print_info "Installing prerequisites..."
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common

    print_info "Adding Docker GPG key..."
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -

    print_info "Adding Docker repository..."
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

    print_info "Updating package index again..."
    apt-get update

    print_info "Installing Docker CE..."
    apt-get install -y docker-ce

    print_success "Docker CE installed successfully!"
else
    print_info "Docker is already installed."
fi

# Check Docker service
print_info "Checking Docker service status..."
if systemctl is-active --quiet docker; then
    print_success "Docker service is running."
else
    print_warning "Docker service is not running. Starting it now..."
    systemctl start docker
    
    if systemctl is-active --quiet docker; then
        print_success "Docker service started successfully."
    else
        print_error "Failed to start Docker service. Please check 'systemctl status docker' for more information."
        exit 1
    fi
fi

# Get current user
if [ -n "$SUDO_USER" ]; then
    CURRENT_USER=$SUDO_USER
else
    CURRENT_USER=$(whoami)
fi

print_info "Adding user '$CURRENT_USER' to the 'docker' group..."
usermod -aG docker $CURRENT_USER

print_info "Setting correct permissions on Docker socket..."
chmod 666 /var/run/docker.sock

print_success "Permissions have been updated!"
print_info "You need to log out and log back in for the group changes to take effect."
print_info "Alternatively, you can run: 'newgrp docker' to update group membership without logging out."

# Test Docker
print_info "Testing Docker access..."
sudo -u $CURRENT_USER docker info &>/dev/null
if [ $? -eq 0 ]; then
    print_success "Docker is working correctly!"
else
    print_warning "Docker command still fails. You may need to log out and log back in."
    print_info "Try running 'newgrp docker' and then 'docker info' to verify access."
fi

echo ""
print_info "After fixing permissions, you can run the deployment script:"
echo "  chmod +x k8s/build-and-deploy-to-ubuntu-k8s.sh"
echo "  ./k8s/build-and-deploy-to-ubuntu-k8s.sh --namespace=l1-monitoring"
echo ""
print_info "Or if you don't need to build Docker images (using pre-built images):"
echo "  chmod +x k8s/fresh-namespace-deployment.sh"
echo "  ./k8s/fresh-namespace-deployment.sh"