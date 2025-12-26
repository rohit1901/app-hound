class AppHound < Formula
  include Language::Python::Virtualenv

  desc "Audit top-level app files and folders on macOS"
  homepage "https://github.com/rohit1901/app-hound"
  url "https://github.com/rohit1901/app-hound/archive/refs/tags/v1.0.1.tar.gz"
  sha256 "f35d854f69df40ee5e16f64cdfc547fd79cc927febdb2f40a9241dc3a40fdca2"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    system "#{bin}/app-hound", "--help"
  end
end
