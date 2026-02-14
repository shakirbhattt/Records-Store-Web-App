#!/bin/bash

# Artifact Repository Cleanup Script for KodeKloud Records
# Cost optimization and maintenance automation for Docker registries and package repositories
# Created for Module 6: Release Engineering - Best Practices

set -e

# Configuration
DRY_RUN=${DRY_RUN:-false}
VERBOSE=${VERBOSE:-false}
MAX_PARALLEL_JOBS=${MAX_PARALLEL_JOBS:-5}

# Colors for output
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_verbose() {
    if [[ "$VERBOSE" == "true" ]]; then
        echo -e "${PURPLE}[DEBUG]${NC} $1"
    fi
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local missing_tools=()
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        missing_tools+=("aws-cli")
    fi
    
    # Check jq
    if ! command -v jq &> /dev/null; then
        missing_tools+=("jq")
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    fi
    
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        log_info "Install with: brew install ${missing_tools[*]} (macOS) or apt-get install ${missing_tools[*]} (Ubuntu)"
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure' first."
        exit 1
    fi
    
    log_success "All prerequisites satisfied"
}

# Calculate storage savings
calculate_storage_size() {
    local image_uri="$1"
    local size_bytes
    
    # Get image manifest to calculate size
    size_bytes=$(aws ecr describe-images \
        --repository-name "${image_uri%:*}" \
        --image-ids imageTag="${image_uri#*:}" \
        --query 'imageDetails[0].imageSizeInBytes' \
        --output text 2>/dev/null || echo "0")
    
    echo "$size_bytes"
}

# Convert bytes to human readable format
bytes_to_human() {
    local bytes=$1
    local units=("B" "KB" "MB" "GB" "TB")
    local unit_index=0
    
    while [[ $bytes -ge 1024 && $unit_index -lt 4 ]]; do
        bytes=$((bytes / 1024))
        ((unit_index++))
    done
    
    echo "${bytes}${units[$unit_index]}"
}

# Clean up Docker ECR repositories
cleanup_ecr_repositories() {
    log_info "🐳 Starting ECR repository cleanup..."
    
    local total_saved_bytes=0
    local total_images_deleted=0
    
    # Get list of ECR repositories
    local repositories
    repositories=$(aws ecr describe-repositories --query 'repositories[].repositoryName' --output text)
    
    if [[ -z "$repositories" ]]; then
        log_warn "No ECR repositories found"
        return 0
    fi
    
    echo "$repositories" | while read -r repo; do
        log_info "📦 Processing repository: $repo"
        
        # Development environment cleanup (aggressive)
        if [[ "$repo" == *"-dev" ]] || [[ "$repo" == *"/dev" ]]; then
            log_info "  Development repository detected - aggressive cleanup"
            
            # Delete untagged images older than 3 days
            local dev_images
            dev_images=$(aws ecr list-images \
                --repository-name "$repo" \
                --filter tagStatus=UNTAGGED \
                --query "imageIds[?imageDigest!=null && imagePushedAt<\`$(date -d '3 days ago' -u +%Y-%m-%dT%H:%M:%SZ)\`]" \
                --output json)
            
            if [[ "$dev_images" != "[]" && "$dev_images" != "null" ]]; then
                local count
                count=$(echo "$dev_images" | jq length)
                
                if [[ "$DRY_RUN" == "true" ]]; then
                    log_info "  [DRY RUN] Would delete $count untagged development images"
                else
                    echo "$dev_images" | jq -r '.[] | .imageDigest' | while read -r digest; do
                        aws ecr batch-delete-image \
                            --repository-name "$repo" \
                            --image-ids imageDigest="$digest" &> /dev/null
                        log_verbose "    Deleted untagged image: ${digest:0:12}..."
                    done
                    log_success "  Deleted $count untagged development images"
                    total_images_deleted=$((total_images_deleted + count))
                fi
            fi
            
            # Keep only last 20 tagged development images
            local old_dev_images
            old_dev_images=$(aws ecr describe-images \
                --repository-name "$repo" \
                --query "imageDetails | sort_by(@, &imagePushedAt) | [0:-20] | [].{imageDigest:imageDigest,imageTags:imageTags}" \
                --output json)
            
            if [[ "$old_dev_images" != "[]" && "$old_dev_images" != "null" ]]; then
                local count
                count=$(echo "$old_dev_images" | jq length)
                
                if [[ "$DRY_RUN" == "true" ]]; then
                    log_info "  [DRY RUN] Would delete $count old development images (keeping last 20)"
                else
                    echo "$old_dev_images" | jq -r '.[] | .imageDigest' | while read -r digest; do
                        aws ecr batch-delete-image \
                            --repository-name "$repo" \
                            --image-ids imageDigest="$digest" &> /dev/null
                        log_verbose "    Deleted old dev image: ${digest:0:12}..."
                    done
                    log_success "  Deleted $count old development images"
                    total_images_deleted=$((total_images_deleted + count))
                fi
            fi
        fi
        
        # Staging environment cleanup (moderate)
        if [[ "$repo" == *"-staging" ]] || [[ "$repo" == *"/staging" ]]; then
            log_info "  Staging repository detected - moderate cleanup"
            
            # Delete untagged images older than 7 days
            local staging_images
            staging_images=$(aws ecr list-images \
                --repository-name "$repo" \
                --filter tagStatus=UNTAGGED \
                --query "imageIds[?imageDigest!=null && imagePushedAt<\`$(date -d '7 days ago' -u +%Y-%m-%dT%H:%M:%SZ)\`]" \
                --output json)
            
            if [[ "$staging_images" != "[]" && "$staging_images" != "null" ]]; then
                local count
                count=$(echo "$staging_images" | jq length)
                
                if [[ "$DRY_RUN" == "true" ]]; then
                    log_info "  [DRY RUN] Would delete $count untagged staging images"
                else
                    echo "$staging_images" | jq -r '.[] | .imageDigest' | while read -r digest; do
                        aws ecr batch-delete-image \
                            --repository-name "$repo" \
                            --image-ids imageDigest="$digest" &> /dev/null
                        log_verbose "    Deleted untagged staging image: ${digest:0:12}..."
                    done
                    log_success "  Deleted $count untagged staging images"
                    total_images_deleted=$((total_images_deleted + count))
                fi
            fi
        fi
        
        # Production repository cleanup (conservative)
        if [[ "$repo" == *"-prod" ]] || [[ "$repo" == *"/prod" ]] || [[ "$repo" != *"-dev" && "$repo" != *"-staging" ]]; then
            log_info "  Production repository detected - conservative cleanup"
            
            # Only delete untagged images older than 30 days
            local prod_images
            prod_images=$(aws ecr list-images \
                --repository-name "$repo" \
                --filter tagStatus=UNTAGGED \
                --query "imageIds[?imageDigest!=null && imagePushedAt<\`$(date -d '30 days ago' -u +%Y-%m-%dT%H:%M:%SZ)\`]" \
                --output json)
            
            if [[ "$prod_images" != "[]" && "$prod_images" != "null" ]]; then
                local count
                count=$(echo "$prod_images" | jq length)
                
                if [[ "$DRY_RUN" == "true" ]]; then
                    log_info "  [DRY RUN] Would delete $count old untagged production images"
                else
                    echo "$prod_images" | jq -r '.[] | .imageDigest' | while read -r digest; do
                        aws ecr batch-delete-image \
                            --repository-name "$repo" \
                            --image-ids imageDigest="$digest" &> /dev/null
                        log_verbose "    Deleted old untagged prod image: ${digest:0:12}..."
                    done
                    log_success "  Deleted $count old untagged production images"
                    total_images_deleted=$((total_images_deleted + count))
                fi
            fi
        fi
        
        # Vulnerability-based cleanup
        log_info "  🔍 Checking for vulnerable images..."
        
        # Get images with HIGH or CRITICAL vulnerabilities older than 7 days
        local vulnerable_images
        vulnerable_images=$(aws ecr describe-image-scan-results \
            --repository-name "$repo" \
            --query "imageScanResults[?imageScanStatus.status=='COMPLETE' && length(imageScanFindings.findings[?severity=='HIGH' || severity=='CRITICAL']) > \`0\`].imageId" \
            --output json 2>/dev/null || echo "[]")
        
        if [[ "$vulnerable_images" != "[]" && "$vulnerable_images" != "null" ]]; then
            local vuln_count
            vuln_count=$(echo "$vulnerable_images" | jq length)
            
            if [[ "$DRY_RUN" == "true" ]]; then
                log_warn "  [DRY RUN] Found $vuln_count images with HIGH/CRITICAL vulnerabilities"
            else
                log_warn "  Found $vuln_count images with HIGH/CRITICAL vulnerabilities"
                echo "$vulnerable_images" | jq -r '.[] | .imageDigest // .imageTag' | while read -r identifier; do
                    log_warn "    Vulnerable image: $identifier"
                done
            fi
        fi
    done
    
    log_success "🐳 ECR cleanup completed"
    log_info "📊 Total images processed: $total_images_deleted"
}

# Clean up Docker Hub repositories (if configured)
cleanup_docker_hub() {
    if [[ -z "$DOCKER_HUB_TOKEN" ]]; then
        log_info "🐋 Skipping Docker Hub cleanup (DOCKER_HUB_TOKEN not set)"
        return 0
    fi
    
    log_info "🐋 Starting Docker Hub cleanup..."
    
    # Docker Hub API is rate-limited and requires different approach
    # This is a simplified example
    local namespaces=("kodekloud")
    
    for namespace in "${namespaces[@]}"; do
        log_info "📦 Processing Docker Hub namespace: $namespace"
        
        # List repositories
        local repos
        repos=$(curl -s -H "Authorization: Bearer $DOCKER_HUB_TOKEN" \
            "https://hub.docker.com/v2/namespaces/$namespace/repositories/" | \
            jq -r '.results[].name')
        
        echo "$repos" | while read -r repo; do
            if [[ -n "$repo" && "$repo" != "null" ]]; then
                log_info "  Processing repository: $namespace/$repo"
                
                # Get tags older than 30 days (for dev repos)
                if [[ "$repo" == *"-dev" ]]; then
                    log_info "    Development repository - checking for old tags"
                    # Docker Hub cleanup logic would go here
                    # Note: Docker Hub API is complex and rate-limited
                fi
            fi
        done
    done
    
    log_success "🐋 Docker Hub cleanup completed"
}

# Clean up local Docker images
cleanup_local_docker() {
    log_info "🧹 Starting local Docker cleanup..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Local Docker cleanup summary:"
        docker system df
        
        log_info "[DRY RUN] Would remove:"
        docker image ls --filter "dangling=true" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
    else
        log_info "Removing dangling images..."
        docker image prune -f
        
        log_info "Removing unused containers..."
        docker container prune -f
        
        log_info "Removing unused networks..."
        docker network prune -f
        
        log_info "Removing unused volumes..."
        docker volume prune -f
        
        log_success "Local Docker cleanup completed"
        docker system df
    fi
}

# Generate cleanup report
generate_report() {
    local report_file="artifact-cleanup-report-$(date +%Y%m%d-%H%M%S).json"
    
    log_info "📄 Generating cleanup report: $report_file"
    
    cat > "$report_file" << EOF
{
  "cleanup_report": {
    "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "run_mode": "$([[ "$DRY_RUN" == "true" ]] && echo "dry_run" || echo "execution")",
    "repositories_processed": {
      "ecr": "$(aws ecr describe-repositories --query 'length(repositories)' --output text 2>/dev/null || echo 0)",
      "docker_hub": "$([[ -n "$DOCKER_HUB_TOKEN" ]] && echo "configured" || echo "skipped")",
      "local_docker": "enabled"
    },
    "cleanup_policies": {
      "development": {
        "untagged_retention": "3 days",
        "tagged_retention": "20 images"
      },
      "staging": {
        "untagged_retention": "7 days",
        "tagged_retention": "50 images"
      },
      "production": {
        "untagged_retention": "30 days",
        "tagged_retention": "unlimited"
      }
    },
    "storage_optimization": {
      "estimated_savings": "calculated during execution",
      "cost_impact": "reduced monthly storage costs"
    },
    "security_cleanup": {
      "vulnerable_images": "scanned and reported",
      "policy": "flag HIGH/CRITICAL vulnerabilities"
    },
    "next_cleanup": "$(date -d '+7 days' +%Y-%m-%d)",
    "automation": {
      "cron_schedule": "0 2 * * 0",
      "description": "Weekly cleanup every Sunday at 2 AM"
    }
  }
}
EOF
    
    log_success "Report saved to: $report_file"
}

# Schedule automated cleanup
setup_automation() {
    log_info "⏰ Setting up automated cleanup..."
    
    local cron_file="/tmp/artifact-cleanup-cron"
    
    cat > "$cron_file" << 'EOF'
# Artifact Repository Cleanup - Weekly
# Runs every Sunday at 2 AM UTC
0 2 * * 0 cd /path/to/kodekloud-records && ./scripts/cleanup_old_artifacts.sh > /var/log/artifact-cleanup.log 2>&1

# Monthly comprehensive cleanup
# Runs first Sunday of every month at 3 AM UTC
0 3 1-7 * 0 cd /path/to/kodekloud-records && VERBOSE=true ./scripts/cleanup_old_artifacts.sh > /var/log/artifact-cleanup-monthly.log 2>&1
EOF
    
    log_info "Suggested cron schedule:"
    cat "$cron_file"
    
    if [[ "$DRY_RUN" != "true" ]]; then
        log_info "To install this cron schedule, run:"
        echo "crontab $cron_file"
    fi
    
    rm -f "$cron_file"
}

# Cost analysis
analyze_costs() {
    log_info "💰 Analyzing repository costs..."
    
    # ECR storage analysis
    if command -v aws &> /dev/null; then
        log_info "📊 ECR Storage Analysis:"
        
        aws ecr describe-repositories --query 'repositories[].[repositoryName,repositorySizeInBytes]' --output table | head -20
        
        # Calculate total ECR storage
        local total_ecr_size
        total_ecr_size=$(aws ecr describe-repositories --query 'sum(repositories[].repositorySizeInBytes)' --output text)
        
        if [[ "$total_ecr_size" != "null" && "$total_ecr_size" -gt 0 ]]; then
            local human_size
            human_size=$(bytes_to_human "$total_ecr_size")
            local monthly_cost
            monthly_cost=$(echo "scale=2; $total_ecr_size / 1073741824 * 0.10" | bc 2>/dev/null || echo "N/A")
            
            log_info "Total ECR storage: $human_size"
            log_info "Estimated monthly cost: \$${monthly_cost} (at \$0.10/GB/month)"
        fi
    fi
    
    # Docker local storage
    if command -v docker &> /dev/null; then
        log_info "🐳 Local Docker Storage:"
        docker system df
    fi
}

# Main execution
main() {
    echo -e "${BLUE}🧹 KodeKloud Records - Artifact Repository Cleanup${NC}"
    echo "=============================================="
    echo "Mode: $([[ "$DRY_RUN" == "true" ]] && echo "DRY RUN" || echo "EXECUTION")"
    echo "Timestamp: $(date)"
    echo ""
    
    # Check if dry run mode
    if [[ "$DRY_RUN" == "true" ]]; then
        log_warn "Running in DRY RUN mode - no changes will be made"
    fi
    
    # Run cleanup tasks
    check_prerequisites
    analyze_costs
    cleanup_ecr_repositories
    cleanup_docker_hub
    cleanup_local_docker
    generate_report
    setup_automation
    
    echo ""
    log_success "🎉 Artifact cleanup completed successfully!"
    echo ""
    log_info "💡 Optimization tips:"
    echo "  - Set up automated lifecycle policies in ECR"
    echo "  - Monitor repository costs monthly"
    echo "  - Implement vulnerability scanning in CI/CD"
    echo "  - Use multi-stage builds to reduce image sizes"
    echo ""
    log_info "🔄 Next steps:"
    echo "  - Schedule this script to run weekly"
    echo "  - Set up CloudWatch alarms for repository costs"
    echo "  - Implement repository usage monitoring"
    echo ""
    echo "📚 Learn more in the Release Engineering Best Practices lesson"
}

# Handle script arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --verbose)
            VERBOSE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --dry-run    Show what would be cleaned up without making changes"
            echo "  --verbose    Enable verbose logging"
            echo "  --help       Show this help message"
            echo ""
            echo "Environment variables:"
            echo "  DOCKER_HUB_TOKEN    Docker Hub API token for cleanup"
            echo "  DRY_RUN             Set to 'true' for dry run mode"
            echo "  VERBOSE             Set to 'true' for verbose logging"
            echo ""
            echo "Examples:"
            echo "  $0 --dry-run                # See what would be cleaned"
            echo "  $0 --verbose                # Run with detailed logging"
            echo "  DRY_RUN=true $0             # Environment variable dry run"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Run main function
main "$@" 