-- Feedback Schema

CREATE TABLE feedback (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  contact TEXT,
  department TEXT,
  feedback_type TEXT NOT NULL,
  subject TEXT NOT NULL,
  message TEXT NOT NULL,
  rating INTEGER,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_feedback_type ON feedback(feedback_type);
CREATE INDEX idx_feedback_date ON feedback(created_at);
CREATE INDEX idx_feedback_email ON feedback(email);

-- Sample data for testing
INSERT INTO feedback (name, email, contact, department, feedback_type, subject, message, rating) VALUES
('John Doe', 'john.doe@example.com', '9876543210', 'Maintenance Department', 'Suggestion', 'Improve dashboard interface', 'The dashboard could benefit from a more intuitive layout with better visibility of critical alerts.', 4),
('Jane Smith', 'jane.smith@example.com', '9876543211', 'Admin', 'Appreciation', 'Excellent system implementation', 'The Drive Logs system has significantly improved our vehicle management efficiency. Great work!', 5);
