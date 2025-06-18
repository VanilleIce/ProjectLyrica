# Security Policy

We take the security of our software and our users' data very seriously. If you discover a security vulnerability in Project Lyrica, we kindly ask you to report it to us responsibly.

### Reporting a Vulnerability

**Please report vulnerabilities via Issues.**

### Responsible Disclosure

We value collaboration with security researchers and advocate for responsible disclosure of security vulnerabilities. We expect:

- Confidentiality during the reporting process  
- A reasonable amount of time to fix the issue before public disclosure  
- Avoidance of any activity that could endanger user data or affect availability  

### Known Security Considerations

Project Lyrica was developed with the following security principles:

- **No Network Communication**: The application does not communicate with external servers (except for the optional update check)  
- **Local File Processing**: All files are processed locally, no uploads to external servers  
- **Sandboxing**: The application runs in a restricted Python environment without administrative privileges  
- **Path Validation**: All file paths are validated for security  

### Disclaimer

We are not responsible for:

- Improper use of the software  
- Damage caused by unauthorized modifications to the software  
- Issues resulting from untrusted song files  
