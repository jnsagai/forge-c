# OPTIONAL (feature 017, T055): a Packer template for platform teams that already build images with Packer.
# Packer is BUSL-1.1, not an OSI open-source licence; the required build path is cloud-init on the stock Ubuntu
# 22.04 cloud image (../cloud-init/user-data.yaml) and nothing in the factory runtime depends on Packer.
# It runs the same provisioning script as the cloud-init and the container stand-in, so all three stay identical.
packer {
  required_plugins {
    qemu = { source = "github.com/hashicorp/qemu", version = "= 1.1.0" }
  }
}

variable "ubuntu_image" { type = string }              # path of the pinned cloud image (recipe.lock.json)
variable "ubuntu_image_sha256" { type = string }       # its pinned sha256
variable "forge_revision" { type = string }            # the factory revision to install
variable "data_volume" {
  type    = string
  default = "/srv/forge-c"
}

source "qemu" "forge-c" {
  iso_url          = var.ubuntu_image
  iso_checksum     = "sha256:${var.ubuntu_image_sha256}"
  disk_image       = true
  format           = "qcow2"
  disk_size        = "50G"
  cpus             = 16
  memory           = 65536
  accelerator      = "kvm"
  headless         = true
  cd_files         = ["../cloud-init/user-data.yaml"]
  cd_label         = "cidata"
  ssh_username     = "forge"
  ssh_timeout      = "30m"
  shutdown_command = "sudo shutdown -P now"
}

build {
  sources = ["source.qemu.forge-c"]
  provisioner "file" {
    source      = "../provision.sh"
    destination = "/tmp/provision.sh"
  }
  provisioner "shell" {
    inline = ["sudo FORGE_REVISION=${var.forge_revision} FORGE_DATA_VOLUME=${var.data_volume} bash /tmp/provision.sh"]
  }
}
